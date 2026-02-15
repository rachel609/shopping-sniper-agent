"""
Product Search Tool
Purpose: Search for product prices across Canadian e-commerce platforms.
         Uses DuckDuckGo as the primary search engine (free, no API key needed).
         Falls back to Google Custom Search API if GOOGLE_API_KEY is valid.
Input: Product query string.
Output: JSON string with search results (title, link, snippet) from target platforms.
Dependencies: config (GOOGLE_API_KEY, GOOGLE_CSE_ID, TARGET_PLATFORMS, is_sandbox),
              ddgs, requests
"""
import json
import re
import requests
from langchain.tools import tool

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import GOOGLE_API_KEY, GOOGLE_CSE_ID, TARGET_PLATFORMS, is_sandbox


# Mock data returned in sandbox mode
MOCK_SEARCH_RESULTS = [
    {
        "title": "Sony WH-1000XM5 Wireless Headphones - Best Buy Canada",
        "link": "https://www.bestbuy.ca/en-ca/product/sony-wh-1000xm5/16478045",
        "snippet": "Sony WH-1000XM5 Wireless Noise Cancelling Headphones - Black. $349.99 CAD. Free shipping.",
        "platform": "BestBuy Canada"
    },
    {
        "title": "Sony WH-1000XM5 - Newegg Canada",
        "link": "https://www.newegg.ca/sony-wh-1000xm5/p/N82E16826159678",
        "snippet": "Sony WH-1000XM5 Noise Cancelling Headphones. Price: $359.99 CAD. In stock.",
        "platform": "Newegg Canada"
    },
    {
        "title": "Sony WH-1000XM5 - Canada Computers",
        "link": "https://www.canadacomputers.com/product/sony-wh-1000xm5",
        "snippet": "Sony WH-1000XM5 Over-Ear Headphones. $339.00 CAD. Available online and in-store.",
        "platform": "Canada Computers"
    },
    {
        "title": "Sony WH-1000XM5 - Memory Express",
        "link": "https://www.memoryexpress.com/Products/sony-wh-1000xm5",
        "snippet": "Sony WH-1000XM5 Bluetooth Headphones. $345.00 CAD. Ships within 1-2 days.",
        "platform": "Memory Express"
    },
    {
        "title": "Sony WH-1000XM5 - Amazon.ca",
        "link": "https://www.amazon.ca/dp/B09XS7JWHH",
        "snippet": "Sony WH-1000XM5 Wireless Industry Leading Noise Cancelling Headphones. $329.99 CAD. Prime eligible.",
        "platform": "Amazon Canada"
    },
]

# URL patterns that indicate listing/category/search pages (not product pages)
SKIP_URL_PATTERNS = [
    "/p/pl?", "/search?", "/Search/", "/category/",
    "bing.com/aclick", "bing.com/ck/", "/collection/",
    "/SubCategory/", "/s?k=", "GameCentral",
    "/en/995/", "/Gaming-Monitor/SubCategory",
]


def _build_site_query(product: str) -> str:
    """Build a search query scoped to target platform domains."""
    sites = " OR ".join(f"site:{p['domain']}" for p in TARGET_PLATFORMS)
    return f"{product} price CAD ({sites})"


def _match_platform(link: str) -> str:
    """Match a URL to one of the target platforms."""
    for p in TARGET_PLATFORMS:
        if p["domain"] in link:
            return p["name"]
    return "Unknown"


def _extract_model_number(query: str) -> str:
    """Extract product model/SKU number from user query for precise searching.
    Looks for common patterns like LC34G55TWWNXZA, RTX-4070, WH-1000XM5, etc.
    """
    # Pattern: alphanumeric string with mixed letters+digits, at least 6 chars
    # Matches SKUs like LC34G55TWWNXZA, LS27BG402ENXGO, N82E16824022912
    patterns = [
        r'\b([A-Z]{1,3}\d{2,}[A-Z0-9]{3,})\b',      # LC34G55TWWNXZA
        r'\b([A-Z]{2,}\-?\d{3,}[A-Z0-9]*)\b',         # WH-1000XM5
        r'\b(RTX[\s\-]?\d{4}[\s\w]*)\b',               # RTX 4070 Ti
        r'\b(GTX[\s\-]?\d{4}[\s\w]*)\b',               # GTX 1660
        r'\b(RX[\s\-]?\d{4}[\s\w]*)\b',                # RX 7900 XT
    ]
    for pattern in patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


def _is_valid_product_url(link: str) -> bool:
    """Check if a URL looks like a product page (not a listing/search/ad page)."""
    if not link:
        return False
    for skip in SKIP_URL_PATTERNS:
        if skip in link:
            return False
    return True


def _duckduckgo_search(query: str) -> list:
    """Search using DuckDuckGo with multi-query strategy for precision.
    For each platform, tries exact model number first, then broader query.
    """
    try:
        from ddgs import DDGS

        results = []
        seen_links = set()
        model = _extract_model_number(query)

        for platform_info in TARGET_PLATFORMS:
            domain = platform_info["domain"]
            platform_name = platform_info["name"]
            platform_found = False

            # Build query list: exact model first (if found), then broader
            queries = []
            if model:
                queries.append(f"{model} site:{domain}")
            queries.append(f"{query} site:{domain}")

            for site_query in queries:
                if platform_found:
                    break
                try:
                    ddgs = DDGS()
                    raw = ddgs.text(site_query, region="ca-en", max_results=5)
                    for item in raw:
                        link = item.get("href", "")
                        if not _is_valid_product_url(link):
                            continue
                        if link in seen_links:
                            continue
                        seen_links.add(link)
                        results.append({
                            "title": item.get("title", ""),
                            "link": link,
                            "snippet": item.get("body", ""),
                            "platform": platform_name,
                        })
                        platform_found = True
                except Exception:
                    continue

        # If per-site search got nothing, try a broad search as fallback
        if not results:
            ddgs = DDGS()
            raw = ddgs.text(f"{query} price CAD buy canada", region="ca-en", max_results=10)
            for item in raw:
                link = item.get("href", "")
                if link and link not in seen_links and _is_valid_product_url(link):
                    seen_links.add(link)
                    results.append({
                        "title": item.get("title", ""),
                        "link": link,
                        "snippet": item.get("body", ""),
                        "platform": _match_platform(link),
                    })

        return results

    except ImportError:
        return [{"error": "ddgs package not installed. Run: pip install ddgs"}]
    except Exception as e:
        return [{"error": f"DuckDuckGo search failed: {str(e)}"}]


def _google_search(query: str) -> list:
    """Perform a Google Custom Search API call using REST endpoint."""
    try:
        search_url = "https://www.googleapis.com/customsearch/v1"
        full_query = _build_site_query(query)
        params = {
            "key": GOOGLE_API_KEY,
            "cx": GOOGLE_CSE_ID,
            "q": full_query,
            "num": 10,
        }
        response = requests.get(search_url, params=params, timeout=15)

        if response.status_code != 200:
            return None  # Signal to fall back to DuckDuckGo

        data = response.json()
        results = []
        for item in data.get("items", []):
            link = item.get("link", "")
            results.append({
                "title": item.get("title", ""),
                "link": link,
                "snippet": item.get("snippet", ""),
                "platform": _match_platform(link),
            })
        return results
    except Exception:
        return None  # Signal to fall back to DuckDuckGo


def _real_search(query: str) -> tuple:
    """Search for products using available search engines.
    Uses DuckDuckGo as primary (free, no key needed).
    Falls back to Google Custom Search if DDG fails and Google key is valid.
    Returns (results_list, search_engine_name).
    """
    # Primary: DuckDuckGo (free, reliable)
    ddg_results = _duckduckgo_search(query)
    if ddg_results and not any("error" in r for r in ddg_results):
        return ddg_results, "duckduckgo"

    # Fallback: Google Custom Search (if key is configured)
    if GOOGLE_API_KEY and not GOOGLE_API_KEY.startswith("TEST_"):
        google_results = _google_search(query)
        if google_results is not None:
            return google_results, "google"

    # Return whatever DDG gave us (even if empty)
    return ddg_results, "duckduckgo"


@tool
def search_product_prices(query: str) -> str:
    """Search for a product across Canadian e-commerce platforms (BestBuy, Newegg,
    Canada Computers, Memory Express, Amazon.ca). Returns titles, links, snippets
    and platform names for price comparison."""
    if is_sandbox() and GOOGLE_API_KEY.startswith("TEST_"):
        # Full sandbox mode: both Google key is test AND no real xAI key
        results = []
        for item in MOCK_SEARCH_RESULTS:
            personalized = item.copy()
            personalized["title"] = personalized["title"].replace("Sony WH-1000XM5", query)
            personalized["snippet"] = personalized["snippet"].replace("Sony WH-1000XM5", query)
            results.append(personalized)
        return json.dumps({
            "mode": "sandbox",
            "query": query,
            "results_count": len(results),
            "results": results,
        }, indent=2)
    else:
        results, engine = _real_search(query)
        return json.dumps({
            "mode": "live",
            "search_engine": engine,
            "query": query,
            "results_count": len(results),
            "results": results,
        }, indent=2)
