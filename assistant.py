import os
import re
import difflib
import sys
from dotenv import load_dotenv, find_dotenv

# --- Early ENV Load ---
dotenv_path = find_dotenv()
if dotenv_path:
    load_dotenv(dotenv_path, override=True)
    print(f"🔑 Loaded .env from {dotenv_path}")
else:
    print("⚠️ No .env file found. Falling back to system environment variables.")

# Load Groq API key
api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError("❌ GROQ_API_KEY not found in environment! Add to .env or system vars.")
print(f"✅ GROQ_API_KEY loaded, starts with: {api_key[:7]}... ({len(api_key)} chars)")

# --- Test Key Immediately (Before Heavy Imports) ---
print("🧪 Testing Groq API key...")
try:
    from langchain_groq import ChatGroq
    # FIXED: Use recommended model (deprecation replacement)
    test_llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=api_key)
    test_response = test_llm.invoke("Say 'Hello' in 1 word.")
    print(f"✅ API key valid! Model says: {test_response.content}")
except Exception as e:
    print(f"❌ API/Model error: {e}")
    print("💡 Fix: Check https://console.groq.com/docs/deprecations for model updates")
    sys.exit(1)  # Stop early

# --- Now Load Heavy Libs ---
try:
    from fuzzywuzzy import fuzz
    FUZZY_AVAILABLE = True
    print("✅ Fuzzywuzzy available")
except ImportError:
    FUZZY_AVAILABLE = False
    print("⚠️ Fuzzywuzzy not available – using difflib fallback")

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.prompts import ChatPromptTemplate
from langchain.schema.runnable import RunnablePassthrough
from langchain.schema.output_parser import StrOutputParser

# --- Config ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")

if not os.path.exists(CHROMA_DIR):
    raise ValueError(f"❌ Chroma DB not found at {CHROMA_DIR}! Run ingestion first.")

embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vectorstore = Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)

# --- LLM (FIXED: Use recommended model + fallback) ---
MODEL_NAME = "llama-3.3-70b-versatile"  # Recommended replacement
FALLBACK_MODEL = "mixtral-8x7b-32768"   # Stable alternative if needed

llm = ChatGroq(model=MODEL_NAME, api_key=api_key)
print(f"✅ LLM initialized with model: {MODEL_NAME}")

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

# --- Ask Function (unchanged core logic) ---
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
        print("Retrieved document IDs:", [doc.metadata["id"] for doc in docs])
        print(f"Filtered to {len(docs)} unique projects with award '{award_normalized}'")
        print("Sample retrieved content (first 3):")
        for i, doc in enumerate(docs[:3]):
            print(f"Doc {i+1}: ID={doc.metadata['id']}, Awards={doc.metadata['awards']}, Content={doc.page_content[:100]}...")

        return rag_chain.invoke(query)

    except Exception as e:
        return f"⚠️ Error while generating response: {e}"

# --- CLI Testing ---
if __name__ == "__main__":
    print("💡 Developer Inspiration Assistant CLI – Type 'quit' to exit.")
    while True:
        query = input("\nAsk a question: ")
        if query.lower() == "quit":
            break

        # Extract award from query
        award = None
        query_lower = query.lower()
        if "tag" in query_lower:
            match = re.search(r"tag\s+'([^']+)'", query, re.IGNORECASE)
            if match:
                award = match.group(1).lower()
        elif "most innovative project" in query_lower or "most innovative projects" in query_lower:
            award = "most innovative project"
        elif "best overall project" in query_lower or "best overall projects" in query_lower:
            award = "best overall project"

        print(f"Parsed query: {query}, Award: {award}")
        print("🤔 Thinking...")
        response = ask_assistant(query, award=award)
        print(f"\nAssistant: {response}")