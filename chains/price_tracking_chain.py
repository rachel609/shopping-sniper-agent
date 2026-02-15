"""
Price Tracking Chain
Purpose: Main orchestration chain that combines search, price extraction,
         promotion checking, history logging, and notification into a
         single LangChain RunnableSequence pipeline.
Input: dict with "product" key (and optional "threshold" for alerts).
Output: JSON string with full comparison report.
Dependencies: All tools (google_search, price_extractor, promotion_checker, notifier),
              memory_manager, history_logger_chain, langchain
"""
import json
from datetime import datetime
from langchain_core.runnables import RunnableLambda, RunnableSequence

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.google_search_tool import search_product_prices
from tools.promotion_checker import check_promotions
from tools.notifier import notify_price_alert
from memory.memory_manager import log_price_history, get_price_history
from chains.history_logger_chain import history_logger_chain


def _step_search(input_data: dict) -> dict:
    """Step 1: Search for the product across all platforms."""
    product = input_data.get("product", "")
    search_results = search_product_prices.invoke(product)
    input_data["search_results"] = search_results
    input_data["date"] = datetime.now().strftime("%Y-%m-%d")
    return input_data


def _step_check_promotions(input_data: dict) -> dict:
    """Step 2: Check for any active or upcoming promotions."""
    promo_results = check_promotions.invoke(input_data.get("date", ""))
    input_data["promotions"] = promo_results
    return input_data


def _step_log_history(input_data: dict) -> dict:
    """Step 3: Log all found prices to persistent history."""
    log_input = {
        "product": input_data.get("product", ""),
        "date": input_data.get("date", ""),
        "search_results": input_data.get("search_results", "[]"),
    }
    log_result = history_logger_chain.invoke(log_input)
    input_data["history_log"] = log_result
    return input_data


def _step_get_history(input_data: dict) -> dict:
    """Step 4: Retrieve historical price data for trend analysis."""
    product = input_data.get("product", "")
    history = get_price_history.invoke(product)
    input_data["price_history"] = history
    return input_data


def _step_check_alerts(input_data: dict) -> dict:
    """Step 5: If a threshold is set, check if any price is below it and notify."""
    threshold = input_data.get("threshold")
    if not threshold:
        input_data["alert_result"] = json.dumps({"status": "no_threshold_set"})
        return input_data

    threshold = float(threshold)
    search_data = json.loads(input_data.get("search_results", "{}"))
    results = search_data.get("results", [])

    import re
    for r in results:
        snippet = r.get("snippet", "")
        price_match = re.search(r'\$([\d,]+\.?\d*)', snippet)
        if price_match:
            price = float(price_match.group(1).replace(",", ""))
            if price <= threshold:
                alert_data = json.dumps({
                    "product": input_data.get("product", ""),
                    "price": price,
                    "platform": r.get("platform", "Unknown"),
                    "threshold": threshold,
                    "url": r.get("link", ""),
                })
                alert_result = notify_price_alert.invoke(alert_data)
                input_data["alert_result"] = alert_result
                return input_data

    input_data["alert_result"] = json.dumps({
        "status": "above_threshold",
        "threshold": threshold,
        "message": "No prices found below your target.",
    })
    return input_data


def _step_build_report(input_data: dict) -> str:
    """Step 6: Compile the final comparison report."""
    search_data = json.loads(input_data.get("search_results", "{}"))
    promo_data = json.loads(input_data.get("promotions", "{}"))
    history_data = json.loads(input_data.get("price_history", "{}"))

    # Extract and sort prices from search results
    import re
    price_entries = []
    for r in search_data.get("results", []):
        snippet = r.get("snippet", "")
        price_match = re.search(r'\$([\d,]+\.?\d*)', snippet)
        price = 0.0
        if price_match:
            try:
                price = float(price_match.group(1).replace(",", ""))
            except ValueError:
                pass
        price_entries.append({
            "platform": r.get("platform", "Unknown"),
            "price": price,
            "url": r.get("link", ""),
        })

    price_entries.sort(key=lambda x: x["price"] if x["price"] > 0 else float("inf"))

    report = {
        "product": input_data.get("product", ""),
        "date": input_data.get("date", ""),
        "price_comparison": price_entries,
        "best_deal": price_entries[0] if price_entries else None,
        "active_promotions": promo_data.get("active_promotions", []),
        "upcoming_promotions": promo_data.get("upcoming_promotions", []),
        "promotion_advice": promo_data.get("recommendation", ""),
        "price_trend": history_data.get("trend", "no_data"),
        "lowest_recorded": history_data.get("lowest_recorded"),
        "alert": json.loads(input_data.get("alert_result", "{}")),
    }

    return json.dumps(report, indent=2)


# Build the full pipeline as a LangChain RunnableSequence
price_tracking_chain: RunnableSequence = (
    RunnableLambda(_step_search)
    | RunnableLambda(_step_check_promotions)
    | RunnableLambda(_step_log_history)
    | RunnableLambda(_step_get_history)
    | RunnableLambda(_step_check_alerts)
    | RunnableLambda(_step_build_report)
)
