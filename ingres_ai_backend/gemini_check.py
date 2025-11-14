from google import genai
import os

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

print("Listing models visible to this key:")
for m in client.models.list():
    print("-", m.name)
