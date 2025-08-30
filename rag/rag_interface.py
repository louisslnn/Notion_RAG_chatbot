import streamlit as st
from streamlit_chat import message
from notion_ingest import get_note_text
from retriever import build_inmemory_from_texts, ask_pipeline

# --- Streamlit Page Config ---
st.set_page_config(page_title="RAG Chatbot", page_icon="💬", layout="wide")

# --- UI Styling ---
st.markdown(
    """
    <style>
        .main {
            background-color: #f9f9f9;
        }
        .stTextInput > div > div > input {
            border-radius: 12px;
            padding: 10px;
        }
        .stButton > button {
            background-color: #4a90e2;
            color: white;
            border-radius: 8px;
            padding: 0.6em 1.2em;
            font-weight: 600;
        }
        .stButton > button:hover {
            background-color: #3a78c2;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- App Title ---
st.title("🔎 RAG Chatbot")
st.subheader("Ask questions and get AI-powered answers")

# --- Session State for Chat ---
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# --- Chat Display ---
for i, msg in enumerate(st.session_state.messages):
    if msg["role"] == "user":
        message(msg["content"], is_user=True, key=f"user_{i}")
    else:
        message(msg["content"], is_user=False, key=f"bot_{i}")

# --- Input Box ---
with st.form(key="chat_form", clear_on_submit=True):
    user_input = st.text_input("Your message:", "", placeholder="Type your question here...")
    submit = st.form_submit_button("Send")

if submit and user_input:
    # Add user message to chat
    st.session_state.messages.append({"role": "user", "content": user_input})

    # 🔹 Placeholder for your RAG function call
    texts = get_note_text()

    vs = build_inmemory_from_texts(texts)
    response = ask_pipeline(vs, str(user_input)).get('answer')

    # Add bot response
    st.session_state.messages.append({"role": "assistant", "content": response})