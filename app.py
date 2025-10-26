import streamlit as st
import os
import re
import difflib
try:
    from fuzzywuzzy import fuzz
    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False
from dotenv import load_dotenv, find_dotenv
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
from langchain.schema.runnable import RunnablePassthrough
from langchain.schema.output_parser import StrOutputParser

# --- Config ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")

# Load .env
dotenv_path = find_dotenv()
if dotenv_path:
    load_dotenv(dotenv_path, override=True)
    st.write(f"🔑 Loaded .env from {dotenv_path}")
else:
    st.write("⚠️ No .env file found. Falling back to system environment variables.")

# Load Groq API key
api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    st.error("❌ GROQ_API_KEY not found in environment!")
    st.stop()
else:
    st.write(f"✅ GROQ_API_KEY loaded, starts with: {api_key[:7]}...")

# Embeddings (must match ingestion)
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# Reconnect to persistent DB
vectorstore = Chroma(
    persist_directory=CHROMA_DIR,
    embedding_function=embeddings,
)

# --- LLM ---
llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=api_key)

# System prompt
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

# --- Ask Function ---
def ask_assistant(query: str, award: str = None, top_k: int = 500):
    """Query the vectorstore with optional award filter."""
    try:
        # Normalize award for filtering
        award_normalized = award.strip().lower() if award else None

        # Build search parameters
        docs = []
        if award_normalized:
            # Use text search focused on award
            text_query = award_normalized
            retriever = vectorstore.as_retriever(search_kwargs={"k": top_k})
            docs = retriever.invoke(text_query)

            # Post-filter with fuzzy matching
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

            # Deduplicate by ID
            seen_ids = set()
            unique_docs = []
            for doc in filtered_docs:
                if doc.metadata["id"] not in seen_ids:
                    unique_docs.append(doc)
                    seen_ids.add(doc.metadata["id"])
            docs = unique_docs[:5]  # Limit to 5 projects
        else:
            retriever = vectorstore.as_retriever(search_kwargs={"k": top_k})
            docs = retriever.invoke(query)
            # Deduplicate by ID
            seen_ids = set()
            unique_docs = []
            for doc in docs:
                if doc.metadata["id"] not in seen_ids:
                    unique_docs.append(doc)
                    seen_ids.add(doc.metadata["id"])
            docs = unique_docs[:5]

        # Format context
        context = "\n".join([f"Title: {doc.metadata['title']}\nID: {doc.metadata['id']}\nAwards: {doc.metadata['awards']}\nContent: {doc.page_content}" for doc in docs])

        # Build RAG chain
        rag_chain = (
            {"context": lambda x: context, "question": RunnablePassthrough()}
            | prompt
            | llm
            | StrOutputParser()
        )

        # Log for debugging
        st.write("Retrieved document IDs:", [doc.metadata["id"] for doc in docs])
        st.write(f"Filtered to {len(docs)} unique projects with award '{award_normalized}'")
        st.write("Sample retrieved content (first 3):")
        for i, doc in enumerate(docs[:3]):
            st.write(f"Doc {i+1}: ID={doc.metadata['id']}, Awards={doc.metadata['awards']}, Content={doc.page_content[:100]}...")

        return rag_chain.invoke(query)

    except Exception as e:
        return f"⚠️ Error while generating response: {e}"

# --- Streamlit UI ---
st.set_page_config(page_title="Developer Inspiration Assistant", page_icon="💡", layout="wide")
st.title("💡 Developer Inspiration Assistant")
st.markdown("Ask about ReadyTensor publications or projects with specific awards.")

# --- Session state for chat memory ---
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# --- Display the chat log ---
st.markdown("### Chat")
for role, text in st.session_state["messages"]:
    if role == "user":
        st.markdown(f"**You:** {text}")
    else:
        st.markdown(f"**Assistant:** {text}")

# --- Input form at bottom ---
st.markdown("---")
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message:", placeholder="e.g., 'tag \"Best Overall Project\" List 5 projects from this category'")
    submitted = st.form_submit_button("Send")

if submitted and user_input:
    # Extract award from query
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

    st.write(f"Parsed query: {user_input}, Award: {award}")

    # Call the assistant
    with st.spinner("Fetching response..."):
        response = ask_assistant(user_input, award=award)

        # Save both user + assistant messages in session state
        st.session_state["messages"].append(("user", user_input))
        st.session_state["messages"].append(("assistant", response))

    # Force refresh so chat updates immediately
    st.rerun()