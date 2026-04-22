import requests
from fastmcp import FastMCP
import os

# --- CONFIG ---
SERP_URL = "https://serpapi.com/search"
SEMANTIC_SCHOLAR_URL = "https://api.semanticscholar.org/graph/v1"
OPEN_ALEX_URL = "https://api.openalex.org"

# Keys (Remember to move these to .env for production!)
SERP_API_KEY = "d271942f5d6062e893a90abc8d91c110bf6bc2e754e84cf1570336e2e627c5f7"
JINA_API_KEY = "jina_49fff1b8d1b4422b8434d9ab8e55a56baUmUppVtX1WJqq_ls3_hOfXycy2i"
OPEN_ALEX_API_KEY = "pmB1Y2F0RydgYmgkq8OOXq"


mcp = FastMCP("ResearchAgent")

# --- HELPER ---
def reconstruct_abstract(abstract_inverted_index):
    """Reconstruct abstract text from OpenAlex's inverted index format."""
    if not abstract_inverted_index:
        return "Abstract not available."
    try:
        words = {}
        for word, indices in abstract_inverted_index.items():
            for index in indices:
                words[index] = word
        return " ".join([words[i] for i in sorted(words.keys())])
    except Exception:
        return "Abstract reconstruction failed."


def _openalex_search(query: str, limit: int):
    """Internal helper: search OpenAlex and return normalized paper list."""
    oa_params = {"search": query, "per_page": limit}
    headers = {"api-key": OPEN_ALEX_API_KEY} if OPEN_ALEX_API_KEY else {}
    res = requests.get(f"{OPEN_ALEX_URL}/works", params=oa_params, headers=headers, timeout=10)
    res.raise_for_status()
    results = res.json().get("results", [])

    normalized = []
    for r in results:
        normalized.append({
            "paperId": r.get("id"),  # OpenAlex ID (URL form)
            "title": r.get("title"),
            "authors": [{"name": a.get("author", {}).get("display_name")} for a in r.get("authorships", [])],
            "year": r.get("publication_year"),
            "citationCount": r.get("cited_by_count"),
            "url": r.get("doi"),
            "openAccessPdf": {"url": r.get("open_access", {}).get("oa_url")} if r.get("open_access", {}).get("oa_url") else None,
            "abstract": reconstruct_abstract(r.get("abstract_inverted_index")),
            "externalIds": r.get("ids", {}),
            "source": "openalex",
        })
    return normalized



# --- 1. CONSOLIDATED SEARCH (Web & YouTube) ---
@mcp.tool()
def search_web(query: str, required_links: int = 10):
    """
    General search for websites, articles, and YouTube videos.
    The LLM should provide the query (e.g., 'YouTube explanation of Attention is All You Need').
    """
    required_links = min(required_links, 20)
    results = []
    start = 0

    while len(results) < required_links:
        params = {
            "engine": "google",
            "q": query,
            "api_key": SERP_API_KEY,
            "start": start,
        }
        try:
            res = requests.get(SERP_URL, params=params)
            res.raise_for_status()
            data = res.json()
            organic = data.get("organic_results", [])
            if not organic:
                break

            for item in organic:
                results.append({
                    "title": item.get("title"),
                    "link": item.get("link"),
                    "snippet": item.get("snippet"),
                })
            start += 10
        except Exception as e:
            return {"error": f"Search failed: {e}"}

    return results[:required_links]


# --- 2. WEB CONTENT READER ---
@mcp.tool()
def fetch_web_content(url: str) -> str:
    """
    Extracts Markdown text from a URL. Does NOT work for YouTube links.
    """
    if "youtube.com" in url or "youtu.be" in url:
        return "Error: This tool cannot read YouTube videos. Please use a YouTube Transcript tool or summarize based on search snippets."

    reader_url = f"https://r.jina.ai/{url}"
    headers = {"Authorization": f"Bearer {JINA_API_KEY}"}

    try:
        response = requests.get(reader_url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.text
    except Exception as e:
        return f"Error accessing page: {str(e)}"


# --- 3. ACADEMIC ENGINE (Semantic Scholar + OpenAlex fallback) ---
@mcp.tool()
def academic_research(query: str, limit: int = 5):
    """
    Finds research papers, citation counts, and direct PDF links.
    Tries Semantic Scholar first; automatically falls back to OpenAlex if SS is unavailable.
    """
    # 1. Try Semantic Scholar
    search_url = f"{SEMANTIC_SCHOLAR_URL}/paper/search"
    params = {
        "query": query,
        "limit": limit,
        "fields": "paperId,title,authors,year,citationCount,url,openAccessPdf,abstract,externalIds",
    }
    try:
        res = requests.get(search_url, params=params, timeout=10)
        res.raise_for_status()
        data = res.json().get("data", [])
        if data:
            return data
    except Exception as e:
        print(f"[academic_research] Semantic Scholar failed: {e}. Falling back to OpenAlex...")

    # 2. Fallback to OpenAlex
    try:
        return _openalex_search(query, limit)
    except Exception as e:
        return f"Academic search failed (both Semantic Scholar and OpenAlex): {e}"


# --- 4. GET PAPER ID ---
@mcp.tool()
def get_paper_id(query: str):
    """
    Search for a paper by title/keywords and return all available IDs
    (Semantic Scholar paperId, DOI, OpenAlex ID, ArXiv ID).
    Use this first when you need a paper ID for find_related_papers.
    """
    results = academic_research(query, limit=1)
    if isinstance(results, list) and len(results) > 0:
        paper = results[0]
        ext_ids = paper.get("externalIds", {})
        paper_id = paper.get("paperId", "")
        return {
            "title": paper.get("title"),
            "paperId": paper_id,
            "doi": ext_ids.get("DOI") or ext_ids.get("doi"),
            "openalex": ext_ids.get("openalex") or (paper_id if "openalex.org" in str(paper_id) else None),
            "arxiv": ext_ids.get("ArXiv") or ext_ids.get("arxiv"),
            "source": paper.get("source", "semantic_scholar"),
        }
    return "No paper found or an error occurred during ID lookup."


# --- 5. FIND RELATED PAPERS ---
@mcp.tool()
def find_related_papers(paper_id: str, limit: int = 5):
    """
    Finds similar or recommended papers based on a Paper ID.
    Accepts a Semantic Scholar paperId, an OpenAlex ID (URL), or a DOI.
    Use get_paper_id first if you only have a paper title.
    Tries Semantic Scholar recommendations first; falls back to OpenAlex related works.
    """
    # 1. Try Semantic Scholar (only for non-OpenAlex IDs)
    if "openalex.org" not in paper_id:
        rec_url = f"{SEMANTIC_SCHOLAR_URL}/recommendations/papers/{paper_id}"
        params = {"limit": limit, "fields": "paperId,title,authors,year,citationCount,url"}
        try:
            res = requests.get(rec_url, params=params, timeout=10)
            res.raise_for_status()
            return res.json().get("recommendedPapers", [])
        except Exception as e:
            print(f"[find_related_papers] Semantic Scholar failed: {e}. Falling back to OpenAlex...")

    # 2. Fallback: OpenAlex related works
    # Resolve to an OpenAlex-compatible identifier
    if "openalex.org" in paper_id:
        oa_filter = f"related_to:{paper_id}"
    elif paper_id.startswith("10.") or "doi.org" in paper_id:
        doi = paper_id.replace("https://doi.org/", "").replace("http://doi.org/", "")
        oa_filter = f"related_to:doi:{doi}"
    else:
        # Try by Semantic Scholar ID via a title lookup — best effort
        return "Could not find related papers: provide an OpenAlex ID or DOI for the OpenAlex fallback."

    try:
        oa_url = f"{OPEN_ALEX_URL}/works"
        oa_params = {"filter": oa_filter, "per_page": limit}
        headers = {"api-key": OPEN_ALEX_API_KEY} if OPEN_ALEX_API_KEY else {}
        res = requests.get(oa_url, params=oa_params, headers=headers, timeout=10)
        res.raise_for_status()
        results = res.json().get("results", [])
        return [{
            "paperId": r.get("id"),
            "title": r.get("title"),
            "authors": [{"name": a.get("author", {}).get("display_name")} for a in r.get("authorships", [])],
            "year": r.get("publication_year"),
            "citationCount": r.get("cited_by_count"),
            "url": r.get("doi"),
        } for r in results]
    except Exception as e:
        return f"Could not find related papers (both Semantic Scholar and OpenAlex failed): {e}"


if __name__ == "__main__":
    mcp.run(transport="sse", host="0.0.0.0", port=7860) 