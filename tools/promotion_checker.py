"""
Promotion Checker Tool
Purpose: Check if a given date falls within any known Canadian retail promotion event.
Input: Optional date string (YYYY-MM-DD). Defaults to today.
Output: JSON string listing active or upcoming promotions.
Dependencies: config.PROMOTION_EVENTS
"""
import json
from datetime import datetime, timedelta
from langchain.tools import tool

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import PROMOTION_EVENTS


@tool
def check_promotions(date_str: str = "") -> str:
    """Check if a date falls within any known Canadian retail promotion event.
    Returns active promotions and upcoming ones within 30 days.
    Pass a date as YYYY-MM-DD, or leave empty for today."""
    try:
        check_date = datetime.strptime(date_str, "%Y-%m-%d") if date_str else datetime.now()
    except ValueError:
        return json.dumps({"error": f"Invalid date format: {date_str}. Use YYYY-MM-DD."})

    active = []
    upcoming = []

    for event in PROMOTION_EVENTS:
        month = event["month"]
        name = event["name"]

        if "day" in event:
            # Single-day event
            event_start = datetime(check_date.year, month, event["day"])
            event_end = event_start
        elif "day_range" in event:
            # Multi-day event
            event_start = datetime(check_date.year, month, event["day_range"][0])
            event_end = datetime(check_date.year, month, event["day_range"][1])
        else:
            continue

        if event_start <= check_date <= event_end:
            active.append({"name": name, "status": "ACTIVE",
                           "start": event_start.strftime("%Y-%m-%d"),
                           "end": event_end.strftime("%Y-%m-%d")})
        elif 0 < (event_start - check_date).days <= 30:
            upcoming.append({"name": name, "status": "UPCOMING",
                             "starts_in_days": (event_start - check_date).days,
                             "start": event_start.strftime("%Y-%m-%d"),
                             "end": event_end.strftime("%Y-%m-%d")})

    result = {
        "check_date": check_date.strftime("%Y-%m-%d"),
        "active_promotions": active,
        "upcoming_promotions": upcoming,
        "recommendation": ""
    }

    if active:
        result["recommendation"] = f"Great timing! {', '.join(e['name'] for e in active)} is active. Buy now for best deals."
    elif upcoming:
        soonest = min(upcoming, key=lambda x: x["starts_in_days"])
        result["recommendation"] = f"Consider waiting — {soonest['name']} starts in {soonest['starts_in_days']} days."
    else:
        result["recommendation"] = "No major promotions nearby. Compare prices across platforms for the best current deal."

    return json.dumps(result, indent=2)
