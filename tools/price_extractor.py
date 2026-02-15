"""
Price Extractor Tool
Purpose: Extract structured price information from a product page URL or search snippet text.
         Supports two modes:
         1. URL mode: fetch HTML and parse price (may fail due to anti-bot protection)
         2. Snippet mode: extract price from search result text (more reliable)
Input: Product page URL string, OR a JSON string with search result data.
Output: JSON string with product name, price, currency, platform, and URL.
Dependencies: config (TARGET_PLATFORMS, is_sandbox), requests, beautifulsoup4
"""
import json
import re
from datetime import datetime
from langchain.tools import tool

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import TARGET_PLATFORMS, is_sandbox


# Mock price data for sandbox mode
MOCK_PRICES = {
    "bestbuy.ca": {"product": "Sample Product", "price": 349.99, "currency": "CAD", "platform": "BestBuy Canada"},
    "newegg.ca": {"product": "Sample Product", "price": 359.99, "currency": "CAD", "platform": "Newegg Canada"},
    "canadacomputers.com": {"product": "Sample Product", "price": 339.00, "currency": "CAD", "platform": "Canada Computers"},
    "memoryexpress.com": {"product": "Sample Product", "price": 345.00, "currency": "CAD", "platform": "Memory Express"},
    "amazon.ca": {"product": "Sample Product", "price": 329.99, "currency": "CAD", "platform": "Amazon Canada"},
}


def _identify_platform(url: str) -> dict:
    """Identify which target platform a URL belongs to."""
    for p in TARGET_PLATFORMS:
        if p["domain"] in url:
            return p
    return {"name": "Unknown", "domain": "unknown"}


def _extract_price_from_text(text: str) -> float:
    """Extract a CAD price from any text string (HTML, snippet, title, etc.).
    Looks for dollar-sign patterns and returns the first reasonable product price.
    Filters out shipping costs, ratings, and other non-price numbers.
    """
    patterns = [
        # $349.99, $ 349.99, $1,349.99 (most reliable: dollar + cents)
        r'\$\s*([\d,]+\.\d{2})\b',
        # data-price="349.99"
        r'data-price="([\d,]+\.\d{2})"',
        # "price": "349.99" or "price": 349.99
        r'"price"\s*:\s*"?([\d,]+\.\d{2})"?',
    ]
    candidates = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            try:
                price = float(m.replace(",", ""))
                # Filter: must be a reasonable product price (not shipping, not rating)
                if 20.0 < price < 50000.0:
                    candidates.append(price)
            except ValueError:
                continue

    if candidates:
        # Return the most common price, or the first one found
        # (search results often repeat the actual price)
        return candidates[0]
    return 0.0


def _extract_price_cc(soup) -> float:
    """Platform-specific price extraction for Canada Computers.
    CC uses specific HTML patterns for product prices.
    """
    # Try common price CSS selectors used by CC
    selectors = [
        'span.sell-price',
        'span.pq-hdr-product_price',
        'div.pi-prod-price span',
        'span[data-product-price]',
        '.product-page-price span',
    ]
    for sel in selectors:
        elem = soup.select_one(sel)
        if elem:
            price = _extract_price_from_text(elem.get_text())
            if price > 0:
                return price
    # Fallback: look for JSON-LD structured data
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            import json as _json
            data = _json.loads(script.string or '')
            if isinstance(data, dict):
                offers = data.get('offers', {})
                if isinstance(offers, dict) and 'price' in offers:
                    return float(offers['price'])
        except (ValueError, TypeError, KeyError):
            pass
    return 0.0


def _extract_price_newegg(soup) -> float:
    """Platform-specific price extraction for Newegg."""
    selectors = [
        'li.price-current',
        'span.price-current-label + strong',
        'div.product-price span',
    ]
    for sel in selectors:
        elem = soup.select_one(sel)
        if elem:
            price = _extract_price_from_text(elem.get_text())
            if price > 0:
                return price
    return 0.0


def _extract_price_memexpress(soup) -> float:
    """Platform-specific price extraction for Memory Express."""
    selectors = [
        'div.GrandTotal span',
        'div.c-capr-pricing__grand-total',
        'span.c-capr-pricing__grand-total',
    ]
    for sel in selectors:
        elem = soup.select_one(sel)
        if elem:
            price = _extract_price_from_text(elem.get_text())
            if price > 0:
                return price
    return 0.0


def _real_extract(url: str) -> dict:
    """Fetch a URL and extract price information from its HTML.
    Uses platform-specific selectors for better accuracy.
    """
    try:
        import requests
        from bs4 import BeautifulSoup

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else "Unknown Product"
        platform = _identify_platform(url)
        domain = platform.get("domain", "")

        # Try platform-specific extractors first (more accurate)
        price = 0.0
        if "canadacomputers.com" in domain:
            price = _extract_price_cc(soup)
        elif "newegg.ca" in domain:
            price = _extract_price_newegg(soup)
        elif "memoryexpress.com" in domain:
            price = _extract_price_memexpress(soup)

        # Fallback to generic regex extraction from full HTML
        if price <= 0:
            price = _extract_price_from_text(resp.text)

        return {
            "product": title,
            "price": price,
            "currency": "CAD",
            "platform": platform["name"],
            "url": url,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "success": price > 0,
        }
    except Exception as e:
        return {
            "product": "Unknown",
            "price": 0.0,
            "currency": "CAD",
            "platform": _identify_platform(url)["name"],
            "url": url,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "success": False,
            "error": f"Extraction failed: {str(e)}",
        }


def extract_price_from_search_results(search_results_json: str) -> str:
    """Extract prices from search results using a hybrid approach:
    1. First pass: extract prices from snippets/titles (fast, reliable)
    2. Second pass: for platforms with no snippet price, try scraping the URL

    Input: JSON string from search_product_prices tool output.
    Output: JSON string with extracted prices per platform.
    """
    try:
        data = json.loads(search_results_json)
        results = data.get("results", [])
    except (json.JSONDecodeError, AttributeError):
        return json.dumps({"error": "Invalid search results JSON"})

    seen_platforms = {}
    # Track which platforms have URLs but no snippet price (for fallback scraping)
    fallback_urls = {}

    # Pass 1: Extract from snippets (fast)
    for item in results:
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        link = item.get("link", "")
        platform = item.get("platform", "Unknown")

        combined_text = f"{snippet} {title}"
        price = _extract_price_from_text(combined_text)

        if price > 0:
            # Keep the best (lowest) price per platform
            if platform not in seen_platforms or price < seen_platforms[platform]["price"]:
                seen_platforms[platform] = {
                    "product": title,
                    "price": price,
                    "currency": "CAD",
                    "platform": platform,
                    "url": link,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "success": True,
                    "source": "snippet",
                }
        else:
            # No price in snippet; save URL for fallback scraping
            if platform not in seen_platforms and platform not in fallback_urls:
                # Skip search/listing/category pages, only try product pages
                skip_patterns = ["/p/pl", "/search", "/Search/", "/category/",
                                 "/SubCategory/", "/pl?d=", "GameCentral"]
                if link and not any(pat in link for pat in skip_patterns):
                    fallback_urls[platform] = {"url": link, "title": title}

    # Pass 2: Scrape URLs for platforms missing snippet prices (slower but fills gaps)
    for platform, info in fallback_urls.items():
        if platform in seen_platforms:
            continue  # Already found via snippet
        try:
            scraped = _real_extract(info["url"])
            if scraped.get("success") and scraped.get("price", 0) > 0:
                seen_platforms[platform] = {
                    "product": scraped.get("product", info["title"]),
                    "price": scraped["price"],
                    "currency": "CAD",
                    "platform": platform,
                    "url": info["url"],
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "success": True,
                    "source": "scrape",
                }
        except Exception:
            continue  # Skip if scraping fails

    # Convert to sorted list (lowest price first)
    extracted = sorted(seen_platforms.values(), key=lambda x: x["price"])

    return json.dumps({
        "mode": "live",
        "extraction_method": "hybrid",
        "prices_found": len(extracted),
        "results": extracted,
    }, indent=2)


@tool
def extract_price(input_data: str) -> str:
    """Extract product price from a URL or from search result data.
    Accepts either:
    - A product page URL (e.g. 'https://www.bestbuy.ca/...')
    - A JSON string containing search results from search_product_prices

    When given search results JSON, extracts prices from snippets directly
    (more reliable than scraping each site). When given a URL, fetches the
    page HTML and parses the price.

    Returns JSON with product, price, currency, platform, url, and date."""
    input_str = input_data.strip()

    if is_sandbox():
        # Sandbox mode: return mock data
        if input_str.startswith("http"):
            platform = _identify_platform(input_str)
            domain = platform["domain"]
            mock = MOCK_PRICES.get(domain, {
                "product": "Sample Product",
                "price": 299.99,
                "currency": "CAD",
                "platform": platform["name"],
            })
            result = {
                "mode": "sandbox",
                "product": mock["product"],
                "price": mock["price"],
                "currency": mock["currency"],
                "platform": mock["platform"],
                "url": input_str,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "success": True,
            }
            return json.dumps(result, indent=2)
        else:
            # Mock snippet extraction
            return json.dumps({
                "mode": "sandbox",
                "extraction_method": "snippet",
                "prices_found": 5,
                "results": [
                    {"product": "Sample Product", "price": p["price"],
                     "currency": "CAD", "platform": p["platform"],
                     "url": "https://example.com", "date": datetime.now().strftime("%Y-%m-%d"),
                     "success": True, "source": "snippet"}
                    for p in MOCK_PRICES.values()
                ],
            }, indent=2)

    # Live mode: determine input type
    if input_str.startswith("http"):
        # URL mode: try scraping the page
        result = _real_extract(input_str)
        # If scraping failed, return what we got with a hint
        if not result.get("success"):
            result["hint"] = ("Price extraction from URL failed (site may block bots). "
                              "Try passing search results JSON to extract prices from snippets instead.")
        result["mode"] = "live"
        return json.dumps(result, indent=2)
    else:
        # JSON/snippet mode: extract from search results
        return extract_price_from_search_results(input_str)
