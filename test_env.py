import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

# Get the API key
groq_api_key = os.getenv("GROQ_API_KEY")

if groq_api_key:
    print("✅ Your Groq API key was loaded successfully!")
    print("API Key:", groq_api_key[:6] + "..." + groq_api_key[-4:])  # Masked for safety
else:
    print("❌ Could not find GROQ_API_KEY in .env file. Check your setup.")
