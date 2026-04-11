from googlesearch import search
import requests
from bs4 import BeautifulSoup
import re
import json
import logging
import urllib.parse
from duckduckgo_search import DDGS

from app.utils.logger import get_logger

logger = get_logger(__name__)

# ─── Shared HTTP config ─────────────────────────────────────────────────────
import random

# ─── Shared HTTP config ─────────────────────────────────────────────────────
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0'
]

def get_headers():
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

# Tags that are pure noise and never contain useful text
NOISE_TAGS = [
    "script", "style", "nav", "footer", "header", "aside",
    "form", "svg", "noscript", "iframe", "button", "input",
    "select", "textarea", "meta", "link", "figure", "figcaption",
    "picture", "img", "video", "audio", "canvas", "map", "object",
]

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _clean_text(text: str, max_chars: int = 10000) -> str:
    """Normalise whitespace and truncate for LLM efficiency."""
    text = re.sub(r'\r\n|\r', '\n', text)
    text = re.sub(r'[ \t]+', ' ', text)           # collapse horizontal whitespace
    text = re.sub(r'\n\s*\n', '\n\n', text)       # max two consecutive blank lines
    text = re.sub(r'^\s+', '', text, flags=re.MULTILINE)  # strip leading spaces per line
    lines = [l.strip() for l in text.splitlines() if l.strip()]   # drop blank lines entirely
    cleaned = '\n'.join(lines)
    
    # Final regex cleanup
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    
    return cleaned[:max_chars]


def _soup_from_html(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def _extract_main_content(soup: BeautifulSoup) -> str:
    """
    Priority extraction order with BeautifulSoup:
      1. <main> element
      2. <article> element
      3. Specific content-heavy classes
      4. The largest <div> block (heuristic)
      5. Full <body>
    """
    # Remove noise before extraction
    for noise in soup(NOISE_TAGS):
        noise.decompose()

    # Remove elements that *look* like ads / navigation by class/id keywords
    _noise_patterns = re.compile(
        r'(cookie|consent|popup|modal|banner|sidebar|advert|sponsor|'
        r'social|share|related|comment|subscribe|newsletter|promo|'
        r'footer|header|nav)',
        re.I
    )
    for tag in soup.find_all(True):
        try:
            class_ids = ' '.join(tag.get('class', [])) if isinstance(tag.get('class'), list) else (tag.get('class') or '')
            class_ids += ' ' + (tag.get('id') or '')
        except AttributeError as e:
            # tag might be a string or something else without .get
            continue
        if _noise_patterns.search(class_ids):
            # Only decompose if it doesn't contain a lot of text (to avoid false positives)
            if len(tag.get_text()) < 500:
                tag.decompose()

    # Priority: <main> → <article>
    for selector in ['main', 'article']:
        el = soup.find(selector)
        if el and len(el.get_text()) > 200:
            return el.get_text(separator='\n')

    # Heuristic: Largest div with many paragraphs
    divs = soup.find_all(['div', 'section'])
    if divs:
        # Sort by text length, but favor those with <p> tags
        def content_score(d):
            return len(d.get_text()) + (len(d.find_all('p')) * 100)
        
        best_div = max(divs, key=content_score)
        text = best_div.get_text(separator='\n')
        if len(text) > 300:
            return text

    body = soup.find('body')
    return body.get_text(separator='\n') if body else soup.get_text(separator='\n')

# ─── Public tool functions ────────────────────────────────────────────────────

def web_search(query: str, domain: str) -> str:
    """
    Search the internet for a given query using DuckDuckGo.
    - query: The search term.
    - domain: Optional website to prioritize (e.g., 'wikipedia.org' or 'openai.com').
    Returns a JSON list of results with title, snippet, and link.
    """
    # 1. Domain scoping
    if domain:
        domain = domain.replace('http://', '').replace('https://', '').split('/')[0]
        query = f"site:{domain} {query}"

    # 2. Time-aware query enhancement
    time_keywords = ['today', 'latest', 'current', 'news', 'price', 'match', 'score']
    if any(k in query.lower() for k in time_keywords):
        from datetime import datetime
        current_date_str = datetime.now().strftime("%Y-%m-%d")
        if current_date_str not in query:
            query += f" {current_date_str}"
            
    # 3. Search execution via DDGS Library
    try:
        results = []
        with DDGS() as ddgs:
            ddgs_results = ddgs.text(query, max_results=8)
            for r in ddgs_results:
                results.append({
                    "title": r.get("title", ""),
                    "snippet": r.get("body", ""),
                    "link": r.get("href", "")
                })
        
        if results:
            return json.dumps(results, indent=2, ensure_ascii=False)
            
        logger.warning(f"DDG Library returned no results for: {query}. Falling back to manual HTML search.")
    except Exception as e:
        logger.error(f"DDG Library error: {e}. Falling back to manual HTML search.")

    # 4. Fallback: Manual HTML Search
    encoded = urllib.parse.quote_plus(query)
    results = _search_duckduckgo(encoded)
    if not results:
        results = _search_bing(encoded)
        
    if not results:
        return json.dumps({"error": f"No search results found for: {query}"})
        
    return json.dumps(results, indent=2, ensure_ascii=False)


def google_search(query: str, domain: str) -> str:
    """
    Detailed search using Google Search. Better for finding official news and specific PDFs/pages.
    - query: The search term.
    - domain: Optional website to prioritize.
    """
    try:
        # Domain scoping
        if domain:
            domain = domain.replace('http://', '').replace('https://', '').split('/')[0]
            query = f"site:{domain} {query}"

        results = []
        # googlesearch-python supports advanced=True for titles/snippets
        # search(query, num_results=10, advanced=True) yields SearchResult objects
        from googlesearch import search
        search_gen = search(query, num_results=8, advanced=True)
        
        for res in search_gen:
            results.append({
                "title": res.title,
                "snippet": res.description,
                "link": res.url
            })
            if len(results) >= 8:
                break
        
        if not results:
             return json.dumps({"error": "No results found on Google."})
             
        return json.dumps(results, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Google search failed: {e}")
        return json.dumps({"error": f"Google search failed: {str(e)}"})


def _search_duckduckgo(encoded_query: str) -> list:
    url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
    try:
        resp = requests.get(url, headers=get_headers(), timeout=12)
        resp.raise_for_status()
        soup = _soup_from_html(resp.text)

        results = []
        # DDG HTML layout — the result container is .result or .web-result
        for container in soup.select('.result, .web-result'):
            title_tag  = container.select_one('a.result__a, h2 a')
            snippet_tag = container.select_one('.result__snippet, .result__body')
            if not title_tag:
                continue
            href = title_tag.get('href', '')
            # DDG redirects — try to pull real URL from query string
            real_url = _extract_ddg_url(href)
            results.append({
                "title": title_tag.get_text(strip=True),
                "snippet": snippet_tag.get_text(strip=True) if snippet_tag else '',
                "link": real_url or href,
            })
            if len(results) >= 8:
                break

        return results
    except Exception as e:
        return []


def _extract_ddg_url(href: str) -> str:
    """DuckDuckGo wraps outbound links with /l/?uddg=<encoded>. Unwrap it."""
    if 'uddg=' in href:
        qs = urllib.parse.urlparse(href).query
        params = urllib.parse.parse_qs(qs)
        uddg = params.get('uddg', [None])[0]
        if uddg:
            return urllib.parse.unquote(uddg)
    return href


def _search_bing(encoded_query: str) -> list:
    url = f"https://www.bing.com/search?q={encoded_query}&count=8"
    try:
        resp = requests.get(url, headers=get_headers(), timeout=12)
        resp.raise_for_status()
        soup = _soup_from_html(resp.text)

        results = []
        for li in soup.select('li.b_algo'):
            title_tag   = li.select_one('h2 a')
            snippet_tag = li.select_one('.b_caption p, .b_snippet')
            if not title_tag:
                continue
            results.append({
                "title": title_tag.get_text(strip=True),
                "snippet": snippet_tag.get_text(strip=True) if snippet_tag else '',
                "link": title_tag.get('href', ''),
            })
            if len(results) >= 8:
                break
        return results
    except Exception:
        return []


def scrape_website(url: str) -> str:
    """
    Scrape the visible text content of a webpage and return clean markdown-style text.
    Only provide a valid, fully-qualified URL (starting with http:// or https://).
    Useful for reading articles, documentation, or any online page in detail.
    """
    if not url.startswith(('http://', 'https://')):
        return f"Invalid URL: '{url}'. Must start with http:// or https://"

    try:
        resp = requests.get(url, headers=get_headers(), timeout=15, allow_redirects=True)
        resp.raise_for_status()

        content_type = resp.headers.get('Content-Type', '').lower()
        if 'text/html' not in content_type and 'text/plain' not in content_type:
            return f"Unsupported content type '{content_type}' at {url}. Only HTML pages are supported."

        soup = _soup_from_html(resp.text)

        # ── Page title ──
        title_tag = soup.find('title')
        title = title_tag.get_text(strip=True) if title_tag else 'No title'

        # ── Meta description ──
        meta_desc = ''
        meta = soup.find('meta', attrs={'name': re.compile(r'^description$', re.I)})
        if meta and meta.get('content'):
            meta_desc = meta['content'].strip()

        # ── Main content ──
        content = _extract_main_content(soup)
        content = _clean_text(content, max_chars=6000)

        output_parts = [f"# {title}"]
        if meta_desc:
            output_parts.append(f"**Summary:** {meta_desc}")
        output_parts.append(f"**Source:** {url}")
        output_parts.append("---")
        output_parts.append(content)

        return '\n\n'.join(output_parts)

    except requests.exceptions.Timeout:
        return f"Timeout: '{url}' took too long to respond."
    except requests.exceptions.ConnectionError:
        return f"Connection error: Could not reach '{url}'."
    except requests.exceptions.HTTPError as e:
        return f"HTTP {e.response.status_code} error fetching '{url}'."
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Failed to scrape '{url}'. Error: {str(e)}"
