import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv("c:/Users/dheer/New folder/chatgpt-clone/backend/.env")

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

chat = client.chats.create(
    model="gemini-2.5-flash",
    config=types.GenerateContentConfig(tools=[{"google_search": {}}])
)

response = chat.send_message("What is crawl4ai Python package? Give me its github url.")
print(response.text)
