import os
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

# Define paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")

# Initialize embeddings (must match those used for indexing)
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# Connect to ChromaDB
try:
    vectorstore = Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)
    print(f"✅ Connected to ChromaDB at {CHROMA_DIR}")

    # Get all documents in the collection
    collection = vectorstore._client.get_collection(name="langchain")  # Default collection name
    all_docs = collection.get(include=["metadatas", "documents"])

    # Print document count
    print(f"Total documents: {len(all_docs['documents'])}")

    # Print sample documents and metadata
    print("\nSample Documents (up to 5):")
    for i, (doc, meta) in enumerate(zip(all_docs["documents"][:5], all_docs["metadatas"][:5])):
        print(f"\nDocument {i+1}:")
        print(f"Content (first 100 chars): {doc[:100]}...")
        print(f"Metadata: {meta}")

    # Test a sample query to verify retrieval
    query = "How can I optimize a Python script for data processing?"
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
    retrieved_docs = retriever.get_relevant_documents(query)
    print(f"\nSample Query: {query}")
    print("Retrieved Documents:")
    for i, doc in enumerate(retrieved_docs):
        print(f"Doc {i+1}: {doc.page_content[:100]}... (Metadata: {doc.metadata})")

except Exception as e:
    print(f"⚠️ Error accessing ChromaDB: {e}")