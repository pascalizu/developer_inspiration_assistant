import streamlit as st
import os
import re
import difflib
from dotenv import load_dotenv, find_dotenv

# ----------------------------------------------------------------------
# 1. PAGE CONFIG + CUSTOM SPINNER CSS (Code-Rain Animation)
# ----------------------------------------------------------------------
st.set_page_config(page_title="Developer Inspiration Assistant", page_icon="Light Bulb", layout="wide")

st.markdown("""
<style>
.stSpinner > div > div {
    background: linear-gradient(90deg, #6366f1, #8b5cf6);
    animation: code-rain 2s infinite linear;
    height: 6px !important;
    border-radius: 3px;
}
@keyframes code-rain {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(100%); }
}
</style>
""", unsafe_allow_html=True)

# ----------------------------------------------------------------------
# 2. ENV + API KEY (Global, Tested Early)
# ----------------------------------------------------------------------
dotenv_path = find_dotenv()
if dotenv_path:
    load_dotenv(dotenv_path, override=True)
    st.sidebar.success(f"Loaded .env from {dotenv_path}")
else:
    st.sidebar.warning("No .env found. Using Streamlit Secrets.")

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    st.error(
        "**GROQ_API_KEY missing!**\n\n"
        "- **Local**: Add to `.env`\n"
        "- **Cloud**: Add to **Settings → Secrets** as:\n"
        "```\nGROQ_API_KEY = \"gsk_...\"\n```"
    )
    st.stop()

# Test key immediately
st.sidebar.info("Testing Groq API key...")
try:
    from langchain_groq import ChatGroq
    test_llm = ChatGroq(model="llama-3.3-70b-versatile", groq_api_key=api_key)
    test_response = test_llm.invoke("Say 'Hello' in 1 word.")
    st.sidebar.success(f"Key valid! Model says: **{test_response.content}**")
except Exception as e:
    st.sidebar.error(f"Key test failed: {e}")
    st.error(f"**Groq error**: {e}\n\nGet a new key: [console.groq.com/keys](https://console.groq.com/keys)")
    st.stop()

# ----------------------------------------------------------------------
# 3. HEAVY IMPORTS + CONFIG
# ----------------------------------------------------------------------
try:
    from fuzzywuzzy import fuzz
    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.prompts import ChatPromptTemplate
from langchain.schema.runnable import RunnablePassthrough
from langchain.schema.output_parser import StrOutputParser

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")

if not os.path.exists(CHROMA_DIR):
    st.error(f"Chroma DB not found at `{CHROMA_DIR}`!\n\nRun your ingestion script first.")
    st.stop()

embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vectorstore = Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)

# ----------------------------------------------------------------------
# 4. DETERMINISTIC LLM (No randomness, reproducible)
# ----------------------------------------------------------------------
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    groq_api_key=api_key,
    temperature=0,      # No creativity → consistent
    top_p=1,            # Full probability
    seed=42,            # Same input → same output
    max_tokens=500
)
st.sidebar.success("LLM ready (deterministic)")

# ----------------------------------------------------------------------
# 5. PROMPT TEMPLATE
# ----------------------------------------------------------------------
template = """
You are the Developer Inspiration Assistant. 
Use ONLY the following context from ReadyTensor publications to answer the user’s question.
List up to 5 projects that match the requested award, including their titles, IDs, and awards from metadata.
A project matches if the award appears in the metadata awards or the chunk content (case-insensitive, allowing minor variations).
If fewer than 5 projects match, list all available matches.
If no projects match or the context is irrelevant, say "I don’t have enough information from ReadyTensor publications to list projects for this award."

Context:
{context}

Question: {question}

Answer as clearly and helpfully as possible, citing the source publication (title and ID).
"""
prompt = ChatPromptTemplate.from_template(template)

# ----------------------------------------------------------------------
# 6. ASK FUNCTION (Core