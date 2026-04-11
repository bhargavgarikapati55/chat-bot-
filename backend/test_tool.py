import os
import json
from google import genai
from dotenv import load_dotenv

load_dotenv("c:/Users/dheer/New folder/chatgpt-clone/backend/.env")

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def dummy_search(query: str) -> str:
    """Useful to search for a query"""
    print(f"Executing dummy_search for {query}")
    return "This is a dummy summary of the search result: 42"

chat = client.chats.create(
    model="gemini-2.5-flash",
    config={'tools': [dummy_search]}
)

print("Sending message...")
response = chat.send_message("Please search for the meaning of life using the dummy search tool.")
print("Response text:", response.text)
if response.function_calls:
    for fc in response.function_calls:
        print("Function call:", fc.name, fc.args)

