# ingestion.py — 100% working version (November 2025)

import os
import json
import re
import shutil
from pathlib import Path

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
import chromadb  # ← needed for client_settings

# --- Config ---
BASE_DIR = Path(__file__).parent
DATA_FILE = BASE_DIR / "data" / "readytensor_publications.json"
CHROMA_DIR = BASE_DIR / "chroma_db"

# Embedding model (fast & great for semantic search)
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# --- Helpers ---
def clean_text(value, default=""):
    """Convert anything to clean string, never return None."""
    if value is None or value == "" or str(value).lower() in {"none", "null", "n/a"}:
        return default
    return str(value).strip()

def normalize_award(award: str) -> str:
    if not award:
        return None
    award = award.strip().lower()
    award = re.sub(r"\s+", " ", award)
    return award

def extract_awards(desc: str, json_awards=None) -> list[str]:
    awards = set(json_awards or [])
    if desc:
        desc_lower = desc.lower()
        patterns = [
            r"award[:\-]?\s*([^\n.,;]+)",
            r"winner of\s+([^\n.,;]+)",
            r"won\s+([^\n.,;]+)",
            r"received\s+([^\n.,;]+)",
        ]
        for pattern in patterns:
            matches = re.findall(pattern, desc, re.IGNORECASE)
            awards.update(normalize_award(m) for m in matches if m)

        # Hard-coded important tags
        if "best overall project" in desc_lower:
            awards.add("best overall project")
        if "most innovative project" in desc_lower:
            awards.add("most innovative project")
        if "best rag implementation" in desc_lower:
            awards.add("best rag implementation")
        if "best use of llms" in desc_lower:
            awards.add("best use of llms")
    return sorted(a for a in awards if a)

def load_json(file_path: Path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def batch_add_documents(vectorstore, documents, batch_size=1000):
    total = len(documents)
    for i in range(0, total, batch_size):
        batch = documents[i:i + batch_size]
        vectorstore.add_documents(batch)
        print(f"Added batch {(i // batch_size) + 1} — {len(batch)} chunks")

# --- Main Ingest Function ---
def ingest():
    print("Starting ingestion...")

    # Fresh start every time (recommended for contests)
    if CHROMA_DIR.exists():
        shutil.rmtree(CHROMA_DIR)
        print(f"Removed old database")

    if not DATA_FILE.exists():
        raise FileNotFoundError(f"Data file not found: {DATA_FILE}")

    publications = load_json(DATA_FILE)
    print(f"Loaded {len(publications)} publications")

    # Text splitter
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,
        chunk_overlap=100,
        length_function=len,
        add_start_index=True,
    )

    documents = []

    for pub in publications:
        desc = clean_text(pub.get("publication_description"), "")
        json_awards = pub.get("awards", [])
        all_awards = extract_awards(desc, json_awards)
        awards_str = " | ".join(all_awards) if all_awards else "none"

        metadata = {
            "id": clean_text(pub.get("id")),
            "username": clean_text(pub.get("username"), "anonymous"),
            "title": clean_text(pub.get("title"), "Untitled Project"),
            "license": clean_text(pub.get("license"), "unknown"),
            "awards": awards_str,
            "source": "readytensor_publication",
        }

        full_text = f"""
Title: {metadata['title']}
Author: {metadata['username']}
Description: {desc}
Awards: {awards_str}
        """.strip()

        chunks = splitter.split_text(full_text)

        for i, chunk in enumerate(chunks):
            documents.append(Document(
                page_content=chunk,
                metadata={**metadata, "chunk_index": i, "total_chunks": len(chunks)}
            ))

        print(f"{metadata['title'][:60]:<60} | Awards: {awards_str or 'none'} | Chunks: {len(chunks)}")

        # Chroma vectorstore — telemetry permanently disabled
    vectorstore = Chroma(
        persist_directory=str(CHROMA_DIR),
        embedding_function=embeddings,
        client_settings=chromadb.Settings(anonymized_telemetry=False)
    )

    print(f"\nAdding {len(documents)} chunks to ChromaDB...")
    batch_add_documents(vectorstore, documents)

    print(f"\nSUCCESS: Ingested {len(documents)} chunks from {len(publications)} projects")
    print(f"Database ready at: {CHROMA_DIR}")