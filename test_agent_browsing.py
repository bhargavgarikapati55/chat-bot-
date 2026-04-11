import os
import sys
from dotenv import load_dotenv

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app.services.gemini_service import GeminiService

def test_agent():
    # Handle console encoding for emojis
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    
    load_dotenv(os.path.join('backend', '.env'))
    
    service = GeminiService()
    session_id = "test_agent_session"
    
    prompt = "What is the latest news about OpenAI according to their official blog or news site? Use your browsing tools."
    
    print(f"User: {prompt}")
    print("Agent is thinking and browsing...")
    
    results = []
    for chunk in service.send_message_stream(session_id, prompt):
        if chunk.startswith("\n\n🔍"):
            print(f"DEBUG: {chunk.strip()}")
        else:
            print(chunk, end="", flush=True)
            results.append(chunk)

    print("\n\n--- Test Completed ---")

if __name__ == "__main__":
    test_agent()
