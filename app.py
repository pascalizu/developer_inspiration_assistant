import streamlit as st
import os
import re
import difflib
from dotenv import load_dotenv, find_dotenv

# ----------------------------------------------------------------------
# 1. EARLY GLOBAL KEY LOAD (fixes NameError – api_key defined here)
# ----------------------------------------------------------------------
st.set_page_config(page_title="Developer Inspiration Assistant", page_icon="💡", layout="wide")

dotenv_path = find_dotenv()
if dotenv_path:
    load_dotenv(dotenv_path, override=True)
    st.sidebar.success(f"🔑 Loaded .env from {dotenv_path}")
else:
    st.sidebar.warning("⚠️ No .env file found. Using Streamlit Secrets.")

# GLOBAL: Load & validate key (use this everywhere)
api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    st.error(
        "❌ GROQ_API_KEY not found!\n"
        "• **Local**: Add to `.env` file.\n"
        "• **Cloud**: Add to Settings → Secrets (as `GROQ_API_KEY = \"gsk_...\"`).\n"
        "Get a free key: [console.groq.com/keys](https://console.groq.com/keys)"
    )
    st.stop()

# Test key immediately (before imports – faster & catches issues)
st.sidebar.info("🧪 Testing Groq API key...")
try:
    from langchain_groq import ChatGroq
    test_llm = ChatGroq(model="llama-3.3-70b-versatile", groq_api_key=api_key)  # Use groq_api_key param
    test_response = test_llm.invoke("Say 'Hello' in 1 word.")
    st.sidebar.success(f"✅ Key valid! Model: **{test_response.content}**")
except Exception as e:
    st.sidebar.error(f"❌ Key test failed: {e}")
    st.error(f"Groq error: {e}\n\n💡 Revoke old key & create new at [console.groq.com/keys](https://console.groq.com/keys)")
    st.stop()

# ----------------------------------------------------------------------
# 2. NOW LOAD HEAVY IMPORTS (after key success)
# ----------------------------------------------------------------------
try:
    from fuzzywuzzy import fuzz
    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
from langchain.schema.runnable import RunnablePassthrough
from langchain.schema.output_parser import StrOutputParser

# ----------------------------------------------------------------------
# 3. CONFIG (uses global api_key – no NameError)
# ----------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")

if not os.path.exists(CHROMA_DIR):
    st.error(f"❌ Chroma DB missing at {CHROMA_DIR}!\n💡 Run your ingestion script first.")
    st.stop()

embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vectorstore = Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)

# LLM (uses global api_key + preferred param name)
llm = ChatGroq(
    model="llama-3.3-70b-versatile",  # Updated from deprecation
    groq_api_key=api_key,  # FIXED: Explicit param (avoids env fallback issues)
    temperature=0.7
)
st.sidebar.success("✅ LLM ready!")

# System prompt (unchanged)
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
# 4. ASK FUNCTION (uses global api_key – unchanged logic)
# ----------------------------------------------------------------------
def ask_assistant(query: str, award: str = None, top_k: int = 500):
    """Query the vectorstore with optional award filter."""
    try:
        # Normalize award
        award_normalized = award.strip().lower() if award else None

        # Retrieval
        docs = []
        if award_normalized:
            retriever = vectorstore.as_retriever(search_kwargs={"k": top_k})
            docs = retriever.invoke(award_normalized)

            # Fuzzy post-filter
            filtered_docs = []
            for doc in docs:
                awards_str = doc.metadata.get("awards", "none").lower()
                content = doc.page_content.lower()
                matches = False
                if award_normalized in awards_str or award_normalized in content:
                    matches = True
                elif FUZZY_AVAILABLE:
                    if any(fuzz.ratio(award_normalized, a.lower()) > 70 for a in awards_str.split(" | ")):
                        matches = True
                else:
                    if any(difflib.SequenceMatcher(None, award_normalized, a.lower()).ratio() > 0.7 for a in awards_str.split(" | ")):
                        matches = True
                if matches:
                    filtered_docs.append(doc)

            # Dedup by ID
            seen_ids = set()
            unique_docs = [doc for doc in filtered_docs if doc.metadata["id"] not in seen_ids and not seen_ids.add(doc.metadata["id"])]
            docs = unique_docs[:5]
        else:
            retriever = vectorstore.as_retriever(search_kwargs={"k": top_k})
            docs = retriever.invoke(query)
            # Dedup
            seen_ids = set()
            unique_docs = [doc for doc in docs if doc.metadata["id"] not in seen_ids and not seen_ids.add(doc.metadata["id"])]
            docs = unique_docs[:5]

        # Context
        context = "\n".join([f"Title: {doc.metadata['title']}\nID: {doc.metadata['id']}\nAwards: {doc.metadata['awards']}\nContent: {doc.page_content}" for doc in docs])

        # RAG chain
        rag_chain = (
            {"context": lambda x: context, "question": RunnablePassthrough()}
            | prompt
            | llm
            | StrOutputParser()
        )

        # Debug (collapsible in sidebar)
        with st.sidebar.expander("🔍 Debug Logs"):
            st.write("Retrieved IDs:", [doc.metadata["id"] for doc in docs])
            st.write(f"Filtered: {len(docs)} projects (award: '{award_normalized}')")
            for i, doc in enumerate(docs[:3]):
                st.write(f"Doc {i+1}: ID={doc.metadata['id']}, Awards={doc.metadata['awards']}, Content={doc.page_content[:100]}...")

        return rag_chain.invoke(query)

    except Exception as e:
        return f"⚠️ Error: {e}"

# ----------------------------------------------------------------------
# 5. UI
# ----------------------------------------------------------------------
st.title("💡 Developer Inspiration Assistant")
st.markdown("Ask about ReadyTensor projects/awards (e.g., *tag \"Best Overall Project\"*).")

# Chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

for role, text in st.session_state.messages:
    if role == "user":
        st.markdown(f"**You:** {text}")
    else:
        st.markdown(f"**Assistant:** {text}")

# Input
st.markdown("---")
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Your query:", placeholder='e.g., tag "Best Overall Project" List 5 projects')
    submitted = st.form_submit_button("Send")

if submitted and user_input:
    # Extract award
    award = None
    query_lower = user_input.lower()
    if "tag" in query_lower:
        match = re.search(r"tag\s+'([^']+)'", user_input, re.IGNORECASE)
        if match:
            award = match.group(1).lower()
    elif "most innovative project" in query_lower or "most innovative projects" in query_lower:
        award = "most innovative project"
    elif "best overall project" in query_lower or "best overall projects" in query_lower:
        award = "best overall project"

    st.caption(f"Parsed award: {award or 'none'}")

    # SPINNER MAGIC!
    with st.spinner("**Generating inspiration...** 💡"):
        response = ask_assistant(user_input, award=award)

    st.session_state.messages.append(("user", user_input))
    st.session_state.messages.append(("assistant", response))
    st.rerun()