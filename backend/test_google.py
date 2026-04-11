from googlesearch import search
import json

def test_google_search():
    try:
        query = "current price of Ethereum"
        print(f"Searching for: {query}")
        results = []
        # Search for first 5 results
        for url in search(query, num_results=5):
            results.append(url)
        
        print("Search Results:")
        print(json.dumps(results, indent=2))
    except Exception as e:
        print(f"Search failed: {str(e)}")

if __name__ == "__main__":
    test_google_search()
