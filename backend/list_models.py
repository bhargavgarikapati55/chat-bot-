import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
try:
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    with open("models_list.txt", "w") as f:
        for m in client.models.list():
            if 'flash' in m.name:
                f.write(f"{m.name}\n")
except Exception as e:
    with open("models_list.txt", "w") as f:
        f.write(f"Error: {str(e)}\n")
