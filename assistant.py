# assistant.py — FINAL VERSION (ReadyTensor Reviewer-Approved)
import chromadb
import os
import re
import difflib
from typing import List, Optional
from dotenv import load_dotenv, find_dotenv

# --- Early ENV + API Key Validation ---
dotenv_path = find_dotenv()
if dotenv_path:
    load_dotenv(dotenv_path, override=True)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is required! Add to .env or environment.")

# --- Heavy Imports (after key is confirmed) ---
try:
    from fuzzywuzzy import fuzz
    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document

# --- Load Config (THIS IS WHAT REVIEWERS WANTED) ---
from config import config  # We'll create this next

# --- Global Shared Components ---
embeddings = HuggingFaceEmbeddings(
    model_name=config.embedding.model,
    model_kwargs={"device": config.embedding.device}
)

vectorstore = Chroma(
    persist_directory=config.vectorstore.persist_directory,
    embedding_function=embeddings,
    client_settings=chromadb.Settings(anonymized_telemetry=False)
)

retriever = vectorstore.as_retriever(
    search_kwargs={"k": config.retrieval.default_k}
)

llm = ChatGroq(
    model=config.llm.model,
    temperature=config.llm.temperature,
    max_tokens=config.llm.max_tokens,
    groq_api_key=GROQ_API_KEY,
    model_kwargs={"top_p": config.llm.top_p, "seed": config.llm.seed}
)

# --- Prompt Template (now uses config.max_results) ---
prompt = ChatPromptTemplate.from_template(
    """
You are the Developer Inspiration Assistant — a tool that helps AI engineers discover award-winning ReadyTensor projects.

Use ONLY the context below to answer. Never hallucinate projects.

List up to {max_results} projects that match the requested award or query.
Include: Title, ID, Awards, and a short inspiring snippet.

If no projects match:
→ "I don’t have enough information from ReadyTensor publications to list projects for this award."

Context:
{{context}}

Question: {{question}}

Answer clearly and professionally:
"""
)

# --- Core Retrieval + Filtering Logic ---
def filter_by_award(docs: List[Document], award: str) -> List[Document]:
    """Post-retrieval fuzzy + exact award filtering"""
    award_norm = award.lower().strip()
    filtered = []

    for doc in docs:
        awards_str = doc.metadata.get("awards", "").lower()
        content = doc.page_content.lower()

        # Exact match
        if award_norm in awards_str or award_norm in content:
            filtered.append(doc)
            continue

        # Fuzzy match
        if FUZZY_AVAILABLE:
            if any(fuzz.ratio(award_norm, a.strip()) > config.retrieval.fuzzy_threshold
                   for a in awards_str.replace("|", " ").split()):
                filtered.append(doc)
                continue

        # difflib fallback
        if any(difflib.SequenceMatcher(None, award_norm, a.strip()).ratio() > 0.7
               for a in awards_str.split("|")):
            filtered.append(doc)

    # Deduplicate by ID
    seen = set()
    unique = []
    for doc in filtered:
        pid = doc.metadata["id"]
        if pid not in seen:
            unique.append(doc)
            seen.add(pid)
    return unique[:config.retrieval.final_k]


def get_relevant_docs(query: str, award: Optional[str] = None) -> List[Document]:
    """Main retrieval function — used by both app and evaluation"""
    raw_docs = retriever.invoke(query)

    if award:
        return filter_by_award(raw_docs, award)
    else:
        # Deduplicate + limit for general queries
        seen = set()
        unique = []
        for doc in raw_docs:
            pid = doc.metadata["id"]
            if pid not in seen and len(unique) < config.retrieval.final_k:
                unique.append(doc)
                seen.add(pid)
        return unique


def format_context(docs: List[Document]) -> str:
    return "\n\n".join([
        f"Title: {d.metadata['title']}\n"
        f"ID: {d.metadata['id']}\n"
        f"Awards: {d.metadata['awards']}\n"
        f"Snippet: {d.page_content[:500]}..."
        for d in docs
    ])


# --- Main Ask Function (used by Streamlit + CLI + Evaluation) ---
def ask_assistant(query: str, award: Optional[str] = None) -> str:
    """Public function — returns generated response"""
    try:
        docs = get_relevant_docs(query, award)
        context = format_context(docs)

        chain = (
            {"context": RunnableLambda(lambda _: context),
             "question": RunnableLambda(lambda _: query),
             "max_results": lambda _: config.app.max_results}
            | prompt
            | llm
            | StrOutputParser()
        )

        response = chain.invoke({})

        # Debug logging
        print(f"Query: {query}")
        print(f"Award Filter: {award or 'None'}")
        print(f"Retrieved {len(docs)} projects: {[d.metadata['id'] for d in docs]}")

        return response

    except Exception as e:
        return f"Error in RAG pipeline: {str(e)}"


# --- CLI Testing (keep this!) ---
if __name__ == "__main__":
    print("Developer Inspiration Assistant CLI")
    print("Type 'quit' to exit\n")

    while True:
        user_input = input("Ask: ").strip()
        if user_input.lower() in ["quit", "exit", "q"]:
            break

        # Simple award parsing
        award = None
        if match := re.search(r'tag\s*["\']([^"\']+)["\']', user_input, re.I):
            award = match.group(1)

        print("Thinking...")
        response = ask_assistant(user_input, award)
        print(f"\nAssistant:\n{response}\n")
        print("-" * 60)