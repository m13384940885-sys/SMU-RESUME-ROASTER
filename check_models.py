import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load your API key
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

print("🔍 Asking Google for available models...")

# Loop through and print every model your key can use for text generation
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(f"✅ Use this exact name: {m.name}")