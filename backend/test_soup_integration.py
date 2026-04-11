import os
import sys
from dotenv import load_dotenv

# Ensure the app module can be found
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
load_dotenv(".env")

from app.utils.scraper import scrape_website, google_search, web_search

def test_scraping():
    print("=== Testing BeautifulSoup Scraping Integration ===")
    
    # Test URL - using python.org as a stable target
    test_url = "https://www.python.org/downloads/"
    print(f"\n1. Scraping {test_url}...")
    content = scrape_website(test_url)
    
    if "Python" in content and "Download" in content:
        print("[SUCCESS] Scrape success! Found keywords.")
        print(f"Content Length: {len(content)} characters")
        print("Snippet:", content[:200].replace('\n', ' '))
    else:
        print("[FAILURE] Scrape failed or content unexpected.")
        print("Full output:", content)

def test_search():
    print("\n=== Testing Search Integration ===")
    query = "latest news about SpaceX Starship"
    
    print(f"\n2. Testing google_search for: '{query}'")
    g_results = google_search(query)
    if "http" in g_results:
        print("[SUCCESS] Google search success!")
    else:
        print("[FAILURE] Google search failed or returned no hits.")
        print(g_results)
        
    print(f"\n3. Testing web_search (DuckDuckGo) for: '{query}'")
    w_results = web_search(query)
    if "http" in w_results:
        print("[SUCCESS] DuckDuckGo search success!")
    else:
        print("[FAILURE] DuckDuckGo search failed.")
        print(w_results)

if __name__ == "__main__":
    test_scraping()
    test_search()
