import asyncio

from fastmcp import Client
URL = "https://Codemaster67-ResearchPaperMCP.hf.space/sse"

async def main():
    async with Client("https://Codemaster67-ResearchPaperMCP.hf.space/sse") as client:
        result = await client.call_tool("academic_research", {"query": "Attention is All You Need"})
        print(result)


if __name__ == "__main__":
    asyncio.run(main())


