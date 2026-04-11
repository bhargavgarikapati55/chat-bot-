import os
from dotenv import load_dotenv

# Load environment variables from .env file inside backend directory
load_dotenv()

class Config:
    """Base configuration."""
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
    PORT = int(os.environ.get('PORT', 5000))
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    GEMINI_MODEL_NAME = os.environ.get('GEMINI_MODEL_NAME', 'gemini-2.5-flash')
    GEMINI_BACKUP_MODELS = ["gemini-1.5-flash", "gemini-2.5-flash", "gemini-flash-lite-latest", "gemini-2.0-flash"]
    
    # Rate Limiting & Quota configuration
    RATE_LIMIT_DEFAULT = "500 per day; 60 per hour; 15 per minute"
    AGENT_COOLDOWN = 1  # Minimal cool-down between tool calls
    MAX_HISTORY_MESSAGES = 10 # Max messages (turns) to keep in history
    
    # Memory and Agent constraints
    MAX_MESSAGES_PER_SESSION = 50
    MAX_TOOL_CALLS_PER_TURN = 5
