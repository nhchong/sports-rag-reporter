from google import genai
import os

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

print("🔍 Your available models:")
for model in client.models.list():
    if 'generateContent' in model.supported_actions:
        print(f"✅ {model.name}")