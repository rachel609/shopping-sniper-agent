"""
Memory Manager
Purpose: Manage conversation memory (LangChain ChatMessageHistory) and
         persistent price history (JSON file read/write with LangChain @tool wrappers).
Input: Price data entries or product query strings.
Output: Stored/retrieved price history as JSON strings.
Dependencies: config (PRICE_LOG_PATH, PRICE_CHANGE_ALERT_THRESHOLD), langchain
"""
import json
import os
from datetime import datetime
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain.tools import tool

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import PRICE_LOG_PATH, PRICE_CHANGE_ALERT_THRESHOLD


# ----- Conversation Memory (LangChain ChatMessageHistory) -----
# Session-based store: maps session_id -> ChatMessageHistory
_message_store = {}


def get_session_history(session_id: str = "default") -> ChatMessageHistory:
    """Return a ChatMessageHistory for the given session. Creates one if it doesn't exist."""
    if session_id not in _message_store:
        _message_store[session_id] = ChatMessageHistory()
    return _message_store[session_id]


# ----- Price History Persistence -----
def _load_price_log() -> list:
    """Load price history from the JSON file."""
    try:
        if os.path.exists(PRICE_LOG_PATH):
            with open(PRICE_LOG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
    except (json.JSONDecodeError, IOError):
        pass
    return []


def _save_price_log(entries: list) -> None:
    """Save price history entries to the JSON file."""
    os.makedirs(os.path.dirname(PRICE_LOG_PATH), exist_ok=True)
    with open(PRICE_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)


@tool
def log_price_history(entry_json: str) -> str:
    """Log a price data point to persistent history.
    Input: JSON string with keys: product, platform, price, currency, date, url.
    Appends the entry to data/price_log.json and returns confirmation."""
    try:
        entry = json.loads(entry_json)
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid JSON. Expected keys: product, platform, price, currency, date, url."})

    # Validate required fields
    required = ["product", "platform", "price"]
    for field in required:
        if field not in entry:
            return json.dumps({"error": f"Missing required field: {field}"})

    # Normalize entry with defaults
    record = {
        "product": entry["product"],
        "platform": entry["platform"],
        "price": float(entry["price"]),
        "currency": entry.get("currency", "CAD"),
        "date": entry.get("date", datetime.now().strftime("%Y-%m-%d")),
        "url": entry.get("url", ""),
    }

    entries = _load_price_log()
    entries.append(record)
    _save_price_log(entries)

    return json.dumps({
        "status": "logged",
        "total_entries": len(entries),
        "entry": record,
    }, indent=2)


@tool
def get_price_history(product: str) -> str:
    """Retrieve historical price data for a product.
    Returns all logged prices, sorted by date, plus a trend analysis
    (rising/falling/stable) and a price change alert flag if the latest
    change exceeds the configured threshold."""
    entries = _load_price_log()

    # Filter by product (case-insensitive partial match)
    matching = [e for e in entries if product.lower() in e.get("product", "").lower()]

    if not matching:
        return json.dumps({
            "product": product,
            "entries_found": 0,
            "history": [],
            "trend": "no_data",
            "alert": False,
        }, indent=2)

    # Sort by date
    matching.sort(key=lambda x: x.get("date", ""))

    # Analyze trend
    prices = [e["price"] for e in matching if e.get("price")]
    trend = "stable"
    alert = False
    if len(prices) >= 2:
        latest = prices[-1]
        previous = prices[-2]
        if previous > 0:
            change_pct = (latest - previous) / previous
            if change_pct > PRICE_CHANGE_ALERT_THRESHOLD:
                trend = "rising"
            elif change_pct < -PRICE_CHANGE_ALERT_THRESHOLD:
                trend = "falling"
                alert = True

    # Find lowest across platforms
    lowest = min(matching, key=lambda x: x.get("price", float("inf")))

    return json.dumps({
        "product": product,
        "entries_found": len(matching),
        "history": matching,
        "trend": trend,
        "price_alert": alert,
        "lowest_recorded": {
            "price": lowest["price"],
            "platform": lowest["platform"],
            "date": lowest["date"],
        },
    }, indent=2)
