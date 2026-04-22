# 🔬 Research Paper MCP Server

> A powerful **Model Context Protocol (MCP)** server for AI-assisted academic research, hosted on Hugging Face Spaces. Enables LLMs to search the web, read webpages, and discover research papers with citations and PDF links — all through a clean SSE interface.

[![Hugging Face Spaces](https://img.shields.io/badge/🤗%20Hugging%20Face-Spaces-orange)](https://huggingface.co/spaces/Codemaster67/ResearchPaperMCP)
[![FastMCP](https://img.shields.io/badge/Built%20with-FastMCP-blue)](https://github.com/jlowin/fastmcp)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)](https://www.docker.com/)

---

## 🌐 Live Endpoints

| Service | URL |
|---|---|
| **MCP Server (SSE)** | `https://Codemaster67-ResearchPaperMCP.hf.space/sse` |
| **LangChain Agent API** | `https://Codemaster67-GoolgeLangchainAgent.hf.space/` |

---

## 📖 What Is This?

This project is split into two independent services that work together:

- **`MCP_SERVER/`** — A [FastMCP](https://github.com/jlowin/fastmcp) server that exposes research tools as MCP-compatible endpoints, hosted on Hugging Face Spaces via SSE.
- **`langchain_backend/`** — A FastAPI service that wraps the MCP server with a LangGraph ReAct agent (powered by Google Gemini), and exposes a REST chat API consumed by a frontend.

---

## 📁 Project Structure

```
MCP_For_Researcher/
│
├── MCP_SERVER/                   # 🧠 MCP Tool Server (Hugging Face Spaces)
│   ├── mcp_server.py             #   FastMCP server — defines all 5 MCP tools
│   ├── Testmcp.py                #   Quick local test script for MCP tools
│   └── dockerfile                #   Docker config for HF Spaces deployment
│
├── langchain_backend/            # 🤖 LangChain Agent + FastAPI Backend
│   ├── agent.py                  #   FastAPI app — LangGraph ReAct agent + /initialize & /chat endpoints
│   └── TestUI.py                 #   Streamlit test UI for the agent backend
│
└── README.md
```

---

## 🧠 Part 1 — MCP Server (`MCP_SERVER/`)

The MCP server exposes **5 research tools** that any MCP-compatible AI agent can call directly over SSE.

### Available Tools

| Tool | Description |
|---|---|
| 🔍 `search_web` | Google search via SerpAPI — returns titles, links, and snippets |
| 📄 `fetch_web_content` | Extracts full Markdown content from any URL using Jina Reader |
| 📚 `academic_research` | Queries Semantic Scholar (with automatic OpenAlex fallback) |
| 🔗 `get_paper_id` | Resolves a paper title to its DOI, ArXiv ID, and OpenAlex ID |
| 🧩 `find_related_papers` | Finds similar papers by Semantic Scholar / OpenAlex / DOI |

### Tool Reference

#### `search_web(query, required_links)`
General web + YouTube search using Google (via SerpAPI).
```python
search_web(query="attention is all you need explained", required_links=5)
# Returns: [{ title, link, snippet }, ...]
```

#### `fetch_web_content(url)`
Reads and extracts full Markdown text from any webpage. Powered by [Jina Reader](https://jina.ai/reader/). *(No YouTube support.)*
```python
fetch_web_content(url="https://arxiv.org/abs/1706.03762")
# Returns: Full page text as Markdown
```

#### `academic_research(query, limit)`
Searches academic databases. Tries Semantic Scholar first; falls back to OpenAlex automatically.
```python
academic_research(query="transformer models NLP", limit=5)
# Returns: [{ title, authors, year, citationCount, abstract, openAccessPdf, externalIds }, ...]
```

#### `get_paper_id(query)`
Resolves a paper title/keywords to all known identifiers.
```python
get_paper_id(query="BERT pre-training deep bidirectional transformers")
# Returns: { title, paperId, doi, openalex, arxiv, source }
```

#### `find_related_papers(paper_id, limit)`
Finds recommended/similar papers. Accepts Semantic Scholar ID, OpenAlex ID, or DOI.
```python
find_related_papers(paper_id="204e3073870fae3d05bcbc2f6a8e263d9b72e776", limit=5)
# Returns: [{ title, authors, year, citationCount, url }, ...]
```

### Running the MCP Server Locally

```bash
cd MCP_SERVER

# Install dependencies
pip install fastmcp requests

# Run the server (SSE on port 7860)
python mcp_server.py
```

### Docker Deployment (HF Spaces)

```bash
cd MCP_SERVER
docker build -t research-mcp .
docker run -p 7860:7860 research-mcp
```

---

## 🤖 Part 2 — LangChain Agent Backend (`langchain_backend/`)

A **FastAPI** service that acts as the bridge between your frontend and the MCP server. On startup it connects to the live MCP SSE endpoint and fetches all available tools. Users bring their own Gemini API key.



### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/initialize` | Initialize the ReAct agent with your Gemini API key + model |
| `POST` | `/chat` | Send a message (+ optional file) and receive an AI response |

### Running the Agent Backend Locally

```bash
cd langchain_backend

# Install dependencies
pip install fastapi uvicorn langchain-mcp-adapters langchain-google-genai langgraph

# Start the server
python agent.py
# API available at http://localhost:7860
```

### Initialize the Agent

```bash
curl -X POST http://localhost:7860/initialize \
  -F "api_key=YOUR_GOOGLE_GEMINI_API_KEY" \
  -F "model_name=gemini-2.5-flash"
```

### Chat with the Agent

```bash
curl -X POST http://localhost:7860/chat \
  -F "message=Find me the top 5 papers on vision transformers with citation counts"
```

> You can also attach a file (PDF, image, or text) to the `/chat` endpoint as multipart form data.

### Testing with the Streamlit UI

`TestUI.py` provides a quick browser-based interface to test the agent backend without a production frontend:

```bash
cd langchain_backend
pip install streamlit
streamlit run TestUI.py
```

---

## 🔌 Connecting the MCP Server to Other Clients

The MCP SSE endpoint can be used directly by any MCP-compatible client — no LangChain required.

### LangChain / LangGraph

```python
from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient({
    "ResearchAgent": {
        "url": "https://Codemaster67-ResearchPaperMCP.hf.space/sse",
        "transport": "sse"
    }
})
tools = await client.get_tools()
```

### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "ResearchAgent": {
      "url": "https://Codemaster67-ResearchPaperMCP.hf.space/sse",
      "transport": "sse"
    }
  }
}
```

---

## 📦 Tech Stack

| Component | Technology |
|---|---|
| MCP Framework | [FastMCP](https://github.com/jlowin/fastmcp) |
| Web Search | [SerpAPI](https://serpapi.com/) (Google engine) |
| Web Reader | [Jina Reader](https://jina.ai/reader/) (`r.jina.ai`) |
| Academic Search | [Semantic Scholar API](https://api.semanticscholar.org/) + [OpenAlex](https://openalex.org/) |
| Agent Framework | [LangGraph](https://github.com/langchain-ai/langgraph) ReAct Agent |
| LLM | [Google Gemini](https://ai.google.dev/) (via `langchain-google-genai`) |
| Agent Backend | [FastAPI](https://fastapi.tiangolo.com/) + [Uvicorn](https://www.uvicorn.org/) |
| Test UI | [Streamlit](https://streamlit.io/) |
| Hosting | [Hugging Face Spaces](https://huggingface.co/spaces) |
| Containerization | Docker (Python 3.10-slim) |

---

## 🔑 API Keys

### MCP Server (`MCP_SERVER/mcp_server.py`)
These keys are baked into the server. For production, move them to HF Spaces Secrets or environment variables.

| Variable | Service | Purpose |
|---|---|---|
| `SERP_API_KEY` | SerpAPI | Google web search |
| `JINA_API_KEY` | Jina AI | Webpage content extraction |
| `OPEN_ALEX_API_KEY` | OpenAlex | Fallback academic search polite pool |

### LangChain Backend (`langchain_backend/agent.py`)
The **Gemini API key** is provided at runtime by the user via `/initialize` — it is **never stored server-side**.

---

## 🙌 Contributing

Pull requests are welcome! Feel free to open an issue for bugs, feature requests, or new tool ideas.

---

