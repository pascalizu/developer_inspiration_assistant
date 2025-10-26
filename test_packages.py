# test_packages.py
packages = ["openai", "langchain", "chromadb", "sentence_transformers"]

for pkg in packages:
    try:
        __import__(pkg)
        print(f"✅ {pkg} is installed correctly")
    except ImportError as e:
        print(f"❌ {pkg} is MISSING: {e}")
