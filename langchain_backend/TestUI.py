import streamlit as st
import requests
# --- CONFIG ---
BACKEND_URL = "https://Codemaster67-GoolgeLangchainAgent.hf.space/"

st.set_page_config(page_title="MCP Research Agent Test", page_icon="🔬")

st.title("🔬 Research Agent Tester")
st.markdown("Connect to your FastAPI backend and test MCP tool integration.")

# --- SIDEBAR: Initialization ---
with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.text_input("Gemini API Key", type="password")
    model_name = st.selectbox("Model", ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash","gemini-2.5-flash-lite"])
    
    if st.button("Initialize Agent"):
        if api_key and model_name:
            try:
                # FastAPI expects Form data
                payload = {"api_key": api_key, "model_name": model_name}
                response = requests.post(f"{BACKEND_URL}/initialize", data=payload)
                
                if response.status_code == 200:
                    st.success(f"Connected! {model_name} is ready.")
                    st.session_state["initialized"] = True
                else:
                    st.error(f"Error: {response.json().get('detail')}")
            except Exception as e:
                st.error(f"Connection failed: {e}")
        else:
            st.warning("Please provide an API Key.")

# --- CHAT INTERFACE ---
if "messages" not in st.session_state:
    st.session_state.messages = []

if st.session_state.get("initialized"):
    # File Uploader
    uploaded_file = st.file_uploader("Upload a paper (PDF/Image/Txt)", type=["pdf", "png", "jpg", "jpeg", "txt"])

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat Input
    if prompt := st.chat_input("Ask a research question..."):
        # Add user message to UI
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking (and maybe using tools)..."):
                try:
                    # Prepare multipart/form-data
                    form_data = {"message": prompt}
                    files = None
                    if uploaded_file:
                        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}

                    response = requests.post(f"{BACKEND_URL}/chat", data=form_data, files=files)
                    
                    if response.status_code == 200:
                        full_response = response.json().get("response")
                        st.markdown(full_response)
                        st.session_state.messages.append({"role": "assistant", "content": full_response})
                    else:
                        st.error(f"Backend Error: {response.text}")
                except Exception as e:
                    st.error(f"Failed to reach backend: {e}")
else:
    st.info("👈 Please initialize the agent in the sidebar to start chatting.")
