"""
Task Prompt Builder
Purpose: Build structured LangChain prompts from user shopping queries,
         parsing user intent (search, compare, track, alert) and target product info.
Input: Raw user query string.
Output: Formatted prompt string ready for the LLM agent.
Dependencies: langchain (ChatPromptTemplate, PromptTemplate)
"""
import json
from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate


# ----- Intent Classification Prompt -----
INTENT_PROMPT = PromptTemplate(
    input_variables=["user_query"],
    template=(
        "Classify the following shopping query into one of these intents: "
        "SEARCH, COMPARE, TRACK, ALERT.\n\n"
        "Query: {user_query}\n\n"
        "Rules:\n"
        "- SEARCH: user wants to find a product or check its price\n"
        "- COMPARE: user wants to compare prices across platforms\n"
        "- TRACK: user wants to monitor price changes over time\n"
        "- ALERT: user wants to be notified when price drops below a threshold\n\n"
        "Return JSON: {{\"intent\": \"<INTENT>\", \"product\": \"<extracted product name>\", "
        "\"threshold_price\": <number or null>}}"
    ),
)


# ----- Agent System Prompt -----
AGENT_SYSTEM_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are Shopping Sniper Agent, a Canadian e-commerce price comparison assistant. "
     "You help users find the best prices across BestBuy.ca, Newegg.ca, Canada Computers, "
     "Memory Express, and Amazon.ca.\n\n"
     "Available tools:\n"
     "- search_product_prices: Search for a product across all platforms\n"
     "- extract_price: Get exact price from a specific product URL\n"
     "- check_promotions: Check for active or upcoming sales events\n"
     "- notify_price_alert: Send price drop notifications\n"
     "- log_price_history: Save price data points to history\n"
     "- get_price_history: Retrieve historical price data\n\n"
     "Always compare prices across all platforms and recommend the best deal. "
     "Check for active promotions that might affect pricing. "
     "Respond in a clear, structured format with prices in CAD.\n\n"
     "Chat history:\n{chat_history}"),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])


def _parse_intent(user_query: str) -> dict:
    """Parse user intent from query using keyword matching (no LLM call needed)."""
    query_lower = user_query.lower()

    # Determine intent from keywords
    if any(kw in query_lower for kw in ["compare", "vs", "versus", "cheaper", "cheapest", "best price"]):
        intent = "COMPARE"
    elif any(kw in query_lower for kw in ["track", "monitor", "watch", "follow"]):
        intent = "TRACK"
    elif any(kw in query_lower for kw in ["alert", "notify", "tell me when", "drops below", "under"]):
        intent = "ALERT"
    else:
        intent = "SEARCH"

    # Try to extract a threshold price
    threshold = None
    import re
    price_match = re.search(r'\$\s*([\d,]+\.?\d*)', user_query)
    if price_match:
        try:
            threshold = float(price_match.group(1).replace(",", ""))
        except ValueError:
            pass

    # Extract product name (remove common intent words)
    product = user_query
    for word in ["find", "search", "compare", "track", "monitor", "alert",
                 "notify", "price", "prices", "cheapest", "best", "for",
                 "me", "the", "of", "a", "an", "when", "drops", "below",
                 "under", "watch", "follow", "tell"]:
        product = re.sub(rf'\b{word}\b', '', product, flags=re.IGNORECASE)
    product = re.sub(r'\$[\d,.]+', '', product).strip()
    product = re.sub(r'\s+', ' ', product).strip()

    return {"intent": intent, "product": product, "threshold_price": threshold}


@tool
def build_task_prompt(user_query: str) -> str:
    """Parse a user shopping query and build a structured task prompt.
    Identifies the intent (SEARCH/COMPARE/TRACK/ALERT), extracts the product name,
    and returns a JSON object with intent, product, threshold_price, and suggested_actions."""
    parsed = _parse_intent(user_query)

    # Build suggested action plan based on intent
    actions = []
    if parsed["intent"] == "SEARCH":
        actions = [
            f"Search for '{parsed['product']}' across all platforms",
            "Extract prices from top results",
            "Check for active promotions",
            "Return sorted price comparison",
        ]
    elif parsed["intent"] == "COMPARE":
        actions = [
            f"Search for '{parsed['product']}' across all platforms",
            "Extract prices from each platform",
            "Check for active promotions or coupons",
            "Rank platforms by price (lowest first)",
            "Recommend the best deal",
        ]
    elif parsed["intent"] == "TRACK":
        actions = [
            f"Search for '{parsed['product']}' current prices",
            "Log current prices to history",
            "Compare with previous price records",
            "Report price trend (rising/falling/stable)",
        ]
    elif parsed["intent"] == "ALERT":
        actions = [
            f"Search for '{parsed['product']}' current prices",
            f"Check if any price is below ${parsed['threshold_price'] or 'N/A'}",
            "If below threshold, send notification",
            "If above, log current price and set up monitoring",
        ]

    result = {
        "original_query": user_query,
        "intent": parsed["intent"],
        "product": parsed["product"],
        "threshold_price": parsed["threshold_price"],
        "suggested_actions": actions,
    }
    return json.dumps(result, indent=2)
