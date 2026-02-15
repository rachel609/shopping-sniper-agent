"""
History Logger Chain
Purpose: A LangChain RunnableSequence that takes raw price search results,
         parses them, and logs each price entry to persistent history via memory_manager.
Input: JSON string containing search results with prices.
Output: JSON string summarizing what was logged.
Dependencies: memory.memory_manager (log_price_history), langchain
"""
import json
from langchain_core.runnables import RunnableLambda, RunnableSequence

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from memory.memory_manager import log_price_history


def _parse_search_results(input_data: dict) -> list:
    """Extract individual price entries from search results for logging."""
    results_str = input_data.get("search_results", "[]")
    try:
        data = json.loads(results_str) if isinstance(results_str, str) else results_str
    except json.JSONDecodeError:
        return []

    # Handle both raw list and nested {"results": [...]} format
    results = data.get("results", data) if isinstance(data, dict) else data
    if not isinstance(results, list):
        return []

    product = input_data.get("product", "Unknown Product")
    entries = []
    for r in results:
        # Try to extract a price from the snippet
        price = 0.0
        snippet = r.get("snippet", "")
        import re
        price_match = re.search(r'\$([\d,]+\.?\d*)', snippet)
        if price_match:
            try:
                price = float(price_match.group(1).replace(",", ""))
            except ValueError:
                pass

        if price > 0:
            entries.append({
                "product": product,
                "platform": r.get("platform", "Unknown"),
                "price": price,
                "currency": "CAD",
                "date": input_data.get("date", ""),
                "url": r.get("link", ""),
            })
    return entries


def _log_entries(entries: list) -> str:
    """Log each parsed entry via the memory_manager tool."""
    logged = []
    for entry in entries:
        result = log_price_history.invoke(json.dumps(entry))
        logged.append(json.loads(result))

    return json.dumps({
        "status": "history_logged",
        "entries_logged": len(logged),
        "details": logged,
    }, indent=2)


# Build the chain as a LangChain RunnableSequence
history_logger_chain: RunnableSequence = (
    RunnableLambda(_parse_search_results)
    | RunnableLambda(_log_entries)
)
