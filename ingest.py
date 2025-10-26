import os
import json
import re
import shutil
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter

# --- Config ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data", "readytensor_publications.json")
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")

# Use HuggingFace embeddings
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# --- Helpers ---
def normalize_award(award: str) -> str:
    """Normalize award/tag names into a consistent lowercase format."""
    if not award:
        return None
    award = award.strip().lower()
    award = re.sub(r"\s+", " ", award)  # collapse whitespace
    return award

def extract_awards(desc: str, json_awards: list = None):
    """Extract awards/tags from publication_description text and JSON awards."""
    awards = json_awards or []
    if not desc:
        return awards

    # Match "Award: ..." or "Award - ..."
    match_award = re.findall(r"award[:\-]?\s*([^\n.,;]+)", desc, re.IGNORECASE)
    if match_award:
        awards.extend([normalize_award(a) for a in match_award if a])

    # Match "Winner of ..." patterns
    match_winner = re.findall(r"winner of\s*([^\n.,;]+)", desc, re.IGNORECASE)
    if match_winner:
        awards.extend([normalize_award(a) for a in match_winner if a])

    # Match "Received ..." patterns
    match_received = re.findall(r"received\s*([^\n.,;]+)", desc, re.IGNORECASE)
    if match_received:
        awards.extend([normalize_award(a) for a in match_received if a])

    # Match "Won ..." patterns
    match_won = re.findall(r"won\s*([^\n.,;]+)", desc, re.IGNORECASE)
    if match_won:
        awards.extend([normalize_award(a) for a in match_won if a])

    # Explicitly add key awards
    if "best overall project" in desc.lower():
        awards.append("best overall project")
    if "most innovative project" in desc.lower():
        awards.append("most innovative project")

    # Deduplicate and filter out None
    return list(set([a for a in awards if a]))

def load_json(file_path: str):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def batch_add_documents(vectorstore, documents, batch_size=5000):
    """Safely add documents to Chroma in batches."""
    total = len(documents)
    for i in range(0, total, batch_size):
        batch = documents[i:i+batch_size]
        vectorstore.add_documents(batch)
        print(f"🟢 Added batch {i//batch_size + 1} ({len(batch)} docs)")

# --- Main Ingest Function ---
def ingest():
    # Reset DB each run
    if os.path.exists(CHROMA_DIR):
        shutil.rmtree(CHROMA_DIR)
        print(f"🗑️ Removed old Chroma DB at {CHROMA_DIR}")

    if not os.path.exists(DATA_FILE):
        raise FileNotFoundError(f"❌ Could not find {DATA_FILE}")

    publications = load_json(DATA_FILE)
    documents = []

    # Splitter for chunking
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,  # number of characters per chunk
        chunk_overlap=50,
        length_function=len,
        add_start_index=True,
    )

    for pub in publications:
        desc = pub.get("publication_description", "")
        awards = extract_awards(desc, pub.get("awards", []))  # Combine JSON and text awards
        awards_str = " | ".join(awards) if awards else "none"  # Store as pipe-separated string

        metadata = {
            "id": pub.get("id"),
            "username": pub.get("username"),
            "license": pub.get("license"),
            "awards": awards_str,  # Store as string
            "title": pub.get("title"),
            "source": "readytensor_publication"
        }

        # Full text for splitting
        full_text = f"""
        Title: {pub.get('title')}
        Author: {pub.get('username')}
        Description: {desc}
        Awards: {awards_str}
        """

        # Apply chunking
        chunks = splitter.split_text(full_text)
        for i, chunk in enumerate(chunks):
            documents.append(Document(
                page_content=chunk.strip(),
                metadata={**metadata, "chunk": i}
            ))

        # Print sanity check
        print(f"📄 {pub.get('title')} | Awards: {awards_str} | Chunks: {len(chunks)}")

    # Build Chroma DB
    vectorstore = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings,
    )

    # Safe batching
    batch_add_documents(vectorstore, documents, batch_size=5000)

    print(f"✅ Ingested {len(documents)} chunks across {len(publications)} publications into {CHROMA_DIR}")

# --- Run ---
if __name__ == "__main__":
    ingest()