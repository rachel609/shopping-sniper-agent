"""
Shopping Sniper Agent - Main Entry Point
Purpose: Initialize the LangChain Tool Calling Agent with Google Gemini LLM,
         register all tools, attach conversation memory, and run the interactive loop.
Input: User queries via command line.
Output: Agent responses with price comparisons, alerts, and recommendations.
Dependencies: config, all tools, memory_manager, chains, langchain, langchain-google-genai
"""
import sys
import os
import json
import re

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(__file__))

from config import GEMINI_API_KEY, XAI_API_KEY, is_sandbox

from tools.google_search_tool import search_product_prices
from tools.price_extractor import extract_price
from tools.promotion_checker import check_promotions
from tools.task_prompt_builder import build_task_prompt
from tools.notifier import notify_price_alert
from memory.memory_manager import log_price_history, get_price_history, get_session_history
from chains.price_tracking_chain import price_tracking_chain

from langchain_openai import ChatOpenAI
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning, message=".*create_react_agent.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="langgraph.*")
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver


# ----- All registered tools -----
ALL_TOOLS = [
    search_product_prices,
    extract_price,
    check_promotions,
    build_task_prompt,
    notify_price_alert,
    log_price_history,
    get_price_history,
]

# ----- Agent system prompt -----
SYSTEM_PROMPT = (
    "You are Shopping Sniper Agent, a Canadian e-commerce price comparison assistant. "
    "You help users find the best prices across BestBuy.ca, Newegg.ca, Canada Computers, "
    "Memory Express, and Amazon.ca.\n\n"
    "WORKFLOW - Follow these steps for price comparison:\n"
    "1. Use search_product_prices to search for the product. IMPORTANT: always include "
    "the model number or SKU (e.g. LC34G55TWWNXZA) in the search query for precision.\n"
    "2. Use extract_price and pass the FULL JSON output from search_product_prices to it.\n"
    "   This extracts prices from search snippets and scrapes product pages.\n"
    "3. Use check_promotions to check for active/upcoming sales\n"
    "4. Present a clear comparison table sorted by price (lowest first)\n"
    "5. For any platform where no price was found, explain the reason clearly.\n\n"
    "Available tools:\n"
    "- search_product_prices: Search for a product across all platforms\n"
    "- extract_price: Extract prices. Pass search results JSON to extract from snippets,\n"
    "  or pass a URL to scrape a specific page\n"
    "- check_promotions: Check for active or upcoming sales events\n"
    "- build_task_prompt: Parse user intent and build action plan\n"
    "- notify_price_alert: Send price drop notifications\n"
    "- log_price_history: Save price data points to history\n"
    "- get_price_history: Retrieve historical price data\n\n"
    "Always compare prices across all platforms and recommend the best deal. "
    "Check for active promotions that might affect pricing. "
    "Respond in a clear, structured format with prices in CAD."
)


def create_agent():
    """Create and return the LangGraph React Agent with Grok (xAI) LLM and memory."""
    llm = ChatOpenAI(
        model="grok-3-mini",
        api_key=XAI_API_KEY,
        base_url="https://api.x.ai/v1",
        temperature=0.3,
    )

    checkpointer = MemorySaver()

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        agent = create_react_agent(
            model=llm,
            tools=ALL_TOOLS,
            prompt=SYSTEM_PROMPT,
            checkpointer=checkpointer,
        )

    return agent


def run_quick_compare(product: str, threshold: float = None) -> str:
    """Run the price tracking chain directly (no LLM needed, works in sandbox mode).
    This is useful for quick comparisons without requiring a valid Gemini API key."""
    input_data = {"product": product}
    if threshold:
        input_data["threshold"] = threshold
    return price_tracking_chain.invoke(input_data)


def main():
    """Main interactive loop."""
    print("=" * 60)
    print("  Shopping Sniper Agent - Canadian Price Comparison")
    print("=" * 60)

    if is_sandbox():
        print("\n[SANDBOX MODE] Using mock data (test API keys detected).")
        print("Replace keys in .env with real ones for live results.\n")
        print("Commands:")
        print("  Type a product name for quick price comparison")
        print("  Type 'agent' to start the LLM agent (requires real Grok/Gemini key)")
        print("  Type 'quit' to exit\n")

        while True:
            try:
                user_input = input("Search product > ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break

            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                print("Goodbye!")
                break

            if user_input.lower() == "agent":
                print("Agent mode requires a real XAI_API_KEY or GEMINI_API_KEY in .env.")
                print("Set your key and restart to use agent mode.\n")
                continue

            # Quick compare mode (no LLM needed)
            # Check for threshold: "RTX 4070 under $500"
            threshold = None
            threshold_match = re.search(r'under\s+\$?([\d,]+\.?\d*)', user_input, re.IGNORECASE)
            if threshold_match:
                threshold = float(threshold_match.group(1).replace(",", ""))
                user_input = re.sub(r'\s*under\s+\$?[\d,]+\.?\d*', '', user_input, flags=re.IGNORECASE).strip()

            result = run_quick_compare(user_input, threshold)
            report = json.loads(result)

            # Display formatted report
            print(f"\n{'=' * 50}")
            print(f"  Price Comparison: {report['product']}")
            print(f"  Date: {report['date']}")
            print(f"{'=' * 50}")

            print("\n  Platform Rankings (lowest first):")
            for i, entry in enumerate(report.get("price_comparison", []), 1):
                marker = " << BEST DEAL" if i == 1 else ""
                print(f"  {i}. {entry['platform']}: ${entry['price']:.2f} CAD{marker}")

            if report.get("active_promotions"):
                print("\n  Active Promotions:")
                for p in report["active_promotions"]:
                    print(f"  - {p['name']} ({p['start']} to {p['end']})")

            if report.get("upcoming_promotions"):
                print("\n  Upcoming Promotions:")
                for p in report["upcoming_promotions"]:
                    print(f"  - {p['name']} in {p.get('starts_in_days', '?')} days")

            if report.get("promotion_advice"):
                print(f"\n  Advice: {report['promotion_advice']}")

            print(f"\n  Price Trend: {report.get('price_trend', 'N/A')}")
            print(f"{'=' * 50}\n")

    else:
        # Live mode with real API keys — start the LLM agent
        print("\n[LIVE MODE] Connected to Grok LLM.\n")
        print("What can I do:")
        print("  - Search product prices:  e.g. 'find RTX 4070 prices'")
        print("  - Compare across stores:  e.g. 'compare Samsung monitor on BestBuy and Amazon'")
        print("  - Track price changes:    e.g. 'track Sony WH-1000XM5'")
        print("  - Set price alerts:       e.g. 'alert me when RTX 4070 drops below $500'")
        print("  - Check promotions:       e.g. 'any upcoming sales?'")
        print("  - Type 'quit' to exit\n")

        agent = create_agent()
        session_config = {"configurable": {"thread_id": "default"}}

        while True:
            try:
                user_input = input("Shopping Sniper > ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break

            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                print("Goodbye!")
                break

            try:
                response = agent.invoke(
                    {"messages": [("human", user_input)]},
                    config=session_config,
                )
                # Extract the last AI message from the response
                messages = response.get("messages", [])
                if messages:
                    last_msg = messages[-1]
                    content = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
                    print(f"\nAgent: {content}\n")
                else:
                    print(f"\nAgent: {response}\n")
            except Exception as e:
                print(f"\nError: {e}")
                print("Falling back to quick compare mode...\n")
                result = run_quick_compare(user_input)
                print(result)


if __name__ == "__main__":
    main()
