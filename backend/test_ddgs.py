from duckduckgo_search import DDGS
import json

def test_search():
    try:
        # Try a different backend or parameters
        with DDGS() as ddgs:
            # We use 'keywords' instead of query for some versions
            results = list(ddgs.text("Ethereum price today", region='wt-wt', safesearch='off', max_results=5))
            
        print("Search Results:")
        print(json.dumps(results, indent=2))
    except Exception as e:
        print(f"Search failed: {str(e)}")

if __name__ == "__main__":
    test_search()
