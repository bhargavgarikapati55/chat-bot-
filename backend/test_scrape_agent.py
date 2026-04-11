import os
import sys
from dotenv import load_dotenv

# Ensure the app module can be found
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
load_dotenv(".env")

from app.services.gemini_service import GeminiService

def main():
    service = GeminiService()
    session_id = "test_scrape_session_123"
    
    prompt = "Please Google search for 'latest python release version' and use your scrape_website tool to read the main download page or news from python.org."
    print(f"Sending prompt: {prompt}\n")
    
    print("Waiting for response... (This might take a minute as it searches and scrapes!)")
    
    # We will use send_message instead of stream to verify the tool call loop directly
    response = service.send_message(session_id, prompt)
    
    print("\n--- Response ---")
    print(response)

if __name__ == "__main__":
    main()
