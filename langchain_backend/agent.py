import os
import base64
import uvicorn
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from contextlib import asynccontextmanager
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage



# --- GLOBAL STATE ---
MCP_URL = "https://Codemaster67-ResearchPaperMCP.hf.space/sse"

mcp_tools = []
agent_executor = None 


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Fetch tool definitions from HF once when the server starts."""
    global mcp_tools
    try:
        client = MultiServerMCPClient({
            "ResearchAgent": { "url": MCP_URL, "transport": "sse" }
        })
        mcp_tools = await client.get_tools()
        print(f"✅ Tools connected: {len(mcp_tools)}")
    except Exception as e:
        print(f"❌ MCP Connection Failed: {e}")
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://research-agent-heduc5oop-research-paper-agent.vercel.app",
        "http://localhost:3000",   
        "http://localhost:5173",  
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# --- API ENDPOINTS ---

@app.post("/initialize")
async def initialize_agent(api_key: str = Form(...), model_name: str = Form(...)):
    """
    Creates the agent ONE TIME. 
    The frontend calls this once when the user submits their settings.
    """
    global agent_executor, mcp_tools
    
    try:
        # Setup the LLM
        llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=0.1
        )
        
        # Create the Agent and store it globally
        agent_executor = create_react_agent(llm, mcp_tools)
        
        return {"status": "Success", "message": f"Agent initialized with {model_name}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Initialization failed: {str(e)}")



@app.post("/chat")
async def chat(
    message: str = Form(...),
    file: Optional[UploadFile] = File(None)
):
    global agent_executor
    
    if agent_executor is None:
        raise HTTPException(status_code=400, detail="Agent not initialized.")

    message_content = [{"type": "text", "text": message}]
    if file:
        file_bytes = await file.read()
        encoded_file = base64.b64encode(file_bytes).decode("utf-8")
        message_content.append({
            "type": "media",
            "mime_type": file.content_type,
            "data": encoded_file
        })

    try:
        inputs = {"messages": [HumanMessage(content=message_content)]}
        response = await agent_executor.ainvoke(inputs)
        
        # --- NEW: PRINT TOOL CALLS ---
        for msg in response["messages"]:
            # Check if this message contains tool calls
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    print(f"[TOOL CALL]: {tool_call['name']}")
                    print(f"ARGUMENTS]: {tool_call['args']}\n")

        final_answer = ""
        # Loop backwards to find the last assistant message with content
        for msg in reversed(response["messages"]):
            if msg.content:
                if isinstance(msg.content, str):
                    final_answer = msg.content
                elif isinstance(msg.content, list):
                    final_answer = " ".join([
                        part.get("text", "") 
                        for part in msg.content 
                        if isinstance(part, dict) and "text" in part
                    ])
                
                if final_answer.strip():
                    break
        
        return {"response": final_answer}
    except Exception as e:
        print(f"❌ Agent Error: {str(e)}") # Added print for error visibility
        return {"error": f"Agent Error: {str(e)}"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)