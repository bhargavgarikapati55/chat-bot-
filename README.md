# Gemini Chatbot with Research Tools

A premium, modern chatbot interface powered by Google Gemini (Flash 2.5), capable of autonomous web research and deep scraping.

## Features
- **Intelligent Browsing**: Uses Dual Search (DuckDuckGo + Google Search) and BeautifulSoup for scraping.
- **Domain-Aware Research**: Can target specific official websites for high-accuracy information.
- **Self-Healing Rotation**: Automatically switches between backup models if quota limits (429) are reached.
- **Modern UI**: Clean, responsive interface with real-time status updates.
- **Context Preservation**: Smart history management that keeps research data available for follow-up questions.

## Tech Stack
- **Frontend**: HTML5, Vanilla CSS3, Javascript (ES6+)
- **Backend**: Python 3.10+, Flask
- **AI**: Google Gemini API (`google-genai`)
- **Tools**: BeautifulSoup4, duckduckgo-search, googlesearch-python

## Getting Started

1.  **Clone the Repo**:
    ```bash
    git clone https://github.com/bhargavgarikapati55/chat-bot-.git
    cd chat-bot-
    ```

2.  **API Key**:
    Create a `backend/.env` file and add your Gemini API Key:
    ```env
    GEMINI_API_KEY=your_key_here
    ```

3.  **Run the App**:
    ```bash
    cd backend
    pip install -r requirements.txt
    python run.py
    ```
    Open `index.html` in your browser.

## Project Structure
- `backend/`: Flask server and Gemini service.
- `app/utils/scraper.py`: Advanced web scraping and search tools.
- `index.html`: Main frontend interface.
- `script.js`: UI logic and SSE streaming handling.
