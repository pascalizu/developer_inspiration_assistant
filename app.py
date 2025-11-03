# app.py
import os
import re
import streamlit as st
from dotenv import load_dotenv

# ----------------------------------------------------------------------
# 1. LOAD ENV + VALIDATE GROQ KEY
# ----------------------------------------------------------------------
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    st.error("GROQ_API_KEY not found! Create a `.env` file with your key.")
    st.stop()

# Test the key immediately
st.write("Testing Groq API key...")
try:
    from langchain_groq import ChatGroq
    test_llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=api_key)
    test_response = test_llm.invoke("Say 'Hello' in 1 word.")
    st.success(f"API key valid! Model says: **{test_response.content}**")
except Exception as e:
    st.error(f"Invalid or revoked API key: {e}")
    st.info("Get a new key at [console.groq.com/keys](https://console.groq.com/keys)")
    st.stop()

# ----------------------------------------------------------------------
# 2. IMPORTS (after key check)
# ----------------------------------------------------------------------
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.prompts import ChatPromptTemplate
from langchain.schema.runnable import RunnablePassthrough
from langchain.schema.output_parser import StrOutputParser

# ----------------------------------------------------------------------
# 3. CONFIG
# ----------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")

if not os.path.exists(CHROMA_DIR):
    st.error(f"Chroma DB not found at {CHROMA_DIR}")
    st.info("Run your ingestion script first!")
    st.stop()

embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vectorstore = Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)

llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=api_key)

# ----------------------------------------------------------------------
# 4. PROMPT
# ----------------------------------------------------------------------
template = """
You are the Developer Inspiration Assistant.
Use ONLY the context below to answer.

List up to 5 projects matching the award. Include title, ID, awards.
If no match: "I don’t have enough information."

Context:
{context}

Question: {question}
"""
prompt = ChatPromptTemplate.from_template(template)

# ----------------------------------------------------------------------
# 5. ASK FUNCTION
# ----------------------------------------------------------------------
def ask_assistant(query: str, award: str | None = None):
    try:
        # Simple retrieval
        retriever = vectorstore.as_retriever(search_kwargs={"k": 10})
        docs = retriever.invoke(award or query)

        # Deduplicate
        seen = set()
        unique = []
        for d in docs:
            pid = d.metadata.get("id")
            if pid and pid not in seen:
                unique.append(d)
                seen.add(pid)
        docs = unique[:5]

        context = "\n\n".join([
            f"Title: {d.metadata.get('title','')}\n"
            f"ID: {d.metadata.get('id','')}\n"
            f"Awards: {d.metadata.get('awards','')}\n"
            f"Content: {d.page_content[:200]}..."
            for d in docs
        ])

        chain = (
            {"context": lambda x: context, "question": RunnablePassthrough()}
            | prompt
            | llm
            | StrOutputParser()
        )

        return chain.invoke(query)

    except Exception as e:
        return f"Error: {e}"

# ----------------------------------------------------------------------
# 6. UI
# ----------------------------------------------------------------------
st.set_page_config(page_title="Dev Inspiration", page_icon="Light Bulb", layout="wide")
st.title("Light Bulb Developer Inspiration Assistant")

if "messages" not in st.session_state:
    st.session_state.messages = []

for role, msg in st.session_state.messages:
    if role == "user":
        st.markdown(f"**You:** {msg}")
    else:
        st.markdown(f"**Assistant:** {msg}")

with st.form("input_form", clear_on_submit=True):
    user_input = st.text_input("Ask about awards or projects:", placeholder='tag "Best Overall Project"')
    send = st.form_submit_button("Send")

if send and user_input:
    # Extract award
    award = None
    m = re.search(r'tag\s*["\']([^"\']+)["\']', user_input, re.I)
    if m:
        award = m.group(1)

    st.session_state.messages.append(("user", user_input))

    with st.spinner("**Generating inspiration…** Light Bulb"):
        response = ask_assistant(user_input, award)

    st.session_state.messages.append(("assistant", response))
    st.rerun()