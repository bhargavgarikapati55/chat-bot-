import os
from google import genai
from dotenv import load_dotenv

load_dotenv('backend/.env')
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

try:
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents="Hello"
    )
    print("Success:", response.text)
except Exception as e:
    print("Error Type:", type(e).__name__)
    print("Error Message:", str(e))
