import os
from dotenv import load_dotenv, find_dotenv

dotenv_path = find_dotenv()
print("🔍 Using .env file at:", dotenv_path)

# Force load environment variables
load_dotenv(dotenv_path, override=True)

key = os.getenv("GROQ_API_KEY")
if key:
    print("✅ Found GROQ_API_KEY in .env")
    print("Key starts with:", key[:10], "...")
else:
    print("❌ GROQ_API_KEY not found")
