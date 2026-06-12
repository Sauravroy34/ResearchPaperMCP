import os
import base64
import uvicorn
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from contextlib import asynccontextmanager
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver


memory_saver = MemorySaver()

# --- GLOBAL STATE ---
MCP_URL = "https://Codemaster67-ResearchPaperMCP.hf.space/mcp"

mcp_tools = []
agent_executor = None 


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Fetch tool definitions from HF once when the server starts."""
    global mcp_tools
    try:
        client = MultiServerMCPClient({
            "ResearchAgent": { "url": MCP_URL, "transport": "http" }
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
        system_prompt = (
                    "You are a professional research assistant. Your primary goal is to provide "
                    "accurate, evidence-based information. \n\n"
                    "CRITICAL REQUIREMENT: Always cite your sources. Whenever you use a tool "
                    "to retrieve information from the web or academic databases, you must strictly follow these formatting rules: \n"
                    "1. Include inline citations (e.g., [1], [2]) immediately after the specific facts they support.\n"
                    "2. At the very end of your response, create a distinct 'Sources & References' section.\n"
                    "3. In the 'Sources & References' section, format EVERY single source on a NEW, separate line using a numbered list.\n"
                    "4. DO NOT group or combine multiple links onto a single line. Each URL and citation must have its own dedicated line."
                )
        
        # Create the Agent and store it globally
        agent_executor = create_agent(
            llm,                        
            mcp_tools,                  
            system_prompt = system_prompt,
            checkpointer=memory_saver
            )
        
        return {"status": "Success", "message": f"Agent initialized with {model_name}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Initialization failed: {str(e)}")



@app.post("/chat")
async def chat(
    message: str = Form(...),
    session_id: str = Form("default_thread"), 
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
        
        # --- NEW: PASS THREAD ID IN CONFIG ---
        config = {"configurable": {"thread_id": session_id}}
        response = await agent_executor.ainvoke(inputs, config=config)
        
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


@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """
    Clears the LangGraph MemorySaver checkpoints for a specific session/thread ID
    when the user disconnects or refreshes the page.
    """
    global memory_saver
    
    if memory_saver is None:
        return {"status": "Ignored", "message": "No memory saver initialized."}
        
    try:
        # MemorySaver in newer versions of LangGraph uses 'checkpoints' and 'writes' dicts.
        # The keys are typically tuples where the first element is the thread_id.
        
        if hasattr(memory_saver, 'checkpoints'):
            keys_to_delete = [k for k in memory_saver.checkpoints.keys() if k[0] == session_id]
            for k in keys_to_delete:
                del memory_saver.checkpoints[k]
                
        if hasattr(memory_saver, 'writes'):
            keys_to_delete = [k for k in memory_saver.writes.keys() if k[0] == session_id]
            for k in keys_to_delete:
                del memory_saver.writes[k]
                
        if hasattr(memory_saver, 'storage') and session_id in memory_saver.storage:
            del memory_saver.storage[session_id]
            
        print(f"Session {session_id} successfully cleared from memory.")
        return {"status": "Success", "message": f"Session {session_id} cleared."}
        
    except Exception as e:
        print(f"Error clearing session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to clear session")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
