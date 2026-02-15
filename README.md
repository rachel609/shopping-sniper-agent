# Shopping Sniper Agent

A LangChain-powered price comparison agent for Canadian e-commerce. It searches products across five major retailers, extracts real-time prices, tracks historical trends, and pushes alerts when prices drop below your target.

Built with **LangGraph ReAct Agent**, **Grok LLM (xAI)**, and **DuckDuckGo Search**.

---

## Features

- **Multi-Platform Price Comparison** — searches BestBuy.ca, Newegg.ca, Canada Computers, Memory Express, and Amazon.ca in a single query
- **Hybrid Price Extraction** — three-tier strategy: search snippet regex, platform-specific CSS selectors, JSON-LD structured data, with generic regex fallback
- **SKU-First Search Precision** — automatically extracts model numbers (e.g. `LC34G55TWWNXZA`, `RTX 4070`, `WH-1000XM5`) for exact product matching
- **Promotion Calendar Awareness** — detects active and upcoming sales events (Black Friday, Boxing Day, Prime Day, Cyber Monday, etc.)
- **Price History & Trend Analysis** — persistent JSON storage with trend detection (rising / falling / stable) based on configurable thresholds
- **Dual-Channel Notifications** — price drop alerts via Telegram Bot API and SMTP email, with graceful degradation when channels are unconfigured
- **Sandbox / Live Dual Mode** — full pipeline runs with mock data when no API keys are present; swap in real keys for live results

---

## Architecture

```
User Query: "Find RTX 4070 prices"
         |
         v
    +----------+
    |  app.py  |  Determine sandbox or live mode
    +----+-----+
         |
    +----v-------------------+
    |  Live Mode:            |
    |  LangGraph ReAct Agent |  Grok LLM autonomously decides which tools to call
    |  (Tool Calling Loop)   |
    +----+-------------------+
         |
         |  Agent invokes tools step by step
         v
    Step 1: search_product_prices
         |  -> DuckDuckGo per-platform search with site: operators
         |  -> SKU-first query, product name fallback
         |  -> Filters out ads, category pages, listing pages
         v
    Step 2: extract_price
         |  -> Pass 1: regex on search snippets (fast, zero network cost)
         |  -> Pass 2: scrape actual pages for missing platforms (slower)
         |  -> Platform-specific CSS selectors (CC / Newegg / MemExpress)
         |  -> Fallback: JSON-LD -> generic regex
         v
    Step 3: check_promotions
         |  -> Match current date against promotion calendar
         |  -> Flag active sales + upcoming events within 30 days
         v
    Step 4: log_price_history -> price_log.json
         |  -> Persist data points for trend analysis
         |  -> Trend detection: rising / falling / stable (5% threshold)
         v
    Step 5: notify_price_alert (if threshold set)
         |  -> Price below target -> push via Telegram / Email
         |  -> Graceful skip for unconfigured channels
         v
    Final Output: Sorted comparison table + promotions + trend data
```

### Module Dependency Graph

```
app.py (entry point)
  |
  +-- config.py (centralized settings, .env loader)
  |
  +-- tools/
  |     +-- google_search_tool.py ---+
  |     |   (DuckDuckGo + Google)    |
  |     +-- price_extractor.py ------+--> chains/price_tracking_chain.py
  |     |   (hybrid extraction)      |         (main orchestration)
  |     +-- promotion_checker.py ----+
  |     +-- task_prompt_builder.py
  |     +-- notifier.py
  |         (Telegram + Email)
  |
  +-- memory/
  |     +-- memory_manager.py ---------> chains/history_logger_chain.py
  |         (ChatMessageHistory +            (parse + persist prices)
  |          price_log.json)
  |
  +-- chains/
        +-- All chains registered to Agent via app.py
```

### Dual Mode Architecture

```
                        +------------------+
                        |    config.py     |
                        |  is_sandbox()?   |
                        +--------+---------+
                                 |
                    +------------+------------+
                    |                         |
                    v                         v
          +-----------------+      +-------------------+
          |  SANDBOX MODE   |      |    LIVE MODE      |
          +-----------------+      +-------------------+
          | Mock search     |      | DuckDuckGo API    |
          | Mock prices     |      | Real web scraping |
          | Console print   |      | Telegram / Email  |
          | No API keys     |      | Grok LLM agent    |
          | needed          |      | Price persistence |
          +-----------------+      +-------------------+
          |                        |
          v                        v
     Quick Compare            LangGraph ReAct
     (direct chain)           (autonomous agent)
```

---

## Project Structure

```
Shopping_Sniper_Agent/
|-- app.py                            # Main entry point, agent orchestrator
|-- config.py                         # Global config, .env loader, sandbox detection
|-- requirements.txt                  # Python dependencies
|-- .env                              # API keys (user-provided, git-ignored)
|-- .gitignore
|
|-- tools/
|   |-- google_search_tool.py         # DuckDuckGo multi-platform search + SKU extraction
|   |-- price_extractor.py            # Hybrid price extraction (snippet + scrape + CSS)
|   |-- promotion_checker.py          # Sales calendar matching (Black Friday, etc.)
|   |-- task_prompt_builder.py        # User intent parser (search / compare / track / alert)
|   +-- notifier.py                   # Telegram + Email alert delivery
|
|-- memory/
|   +-- memory_manager.py             # Conversation memory + persistent price history
|
|-- chains/
|   |-- price_tracking_chain.py       # Main orchestration chain (6-step pipeline)
|   +-- history_logger_chain.py       # Parse search results -> log to JSON
|
|-- data/
|   +-- price_log.json                # Persistent price history (git-ignored)
|
|-- test_notifier.py                  # Notification system test suite (12 tests)
+-- test_google_search.py             # Search module standalone test
```

---

## Quick Start

### 1. Clone and Install

```bash
git clone https://github.com/YOUR_USERNAME/Shopping-Sniper-Agent.git
cd Shopping-Sniper-Agent
pip install -r requirements.txt
```

### 2. Configure API Keys

Copy the `.env.example` or create `.env` in the project root:

```env
# Required for live mode (LLM agent)
XAI_API_KEY=your_xai_api_key_here

# Optional: Google Custom Search (fallback search engine)
GOOGLE_API_KEY=your_google_api_key
GOOGLE_CSE_ID=your_cse_id

# Optional: Notification channels
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
SMTP_EMAIL=your_email@gmail.com
SMTP_PASSWORD=your_app_password
NOTIFY_EMAIL_TO=recipient@example.com
```

> **No API keys?** The agent runs in sandbox mode with mock data — the full pipeline still works.

### 3. Run

```bash
python app.py
```

**Sandbox mode** (no keys):
```
Search product > Samsung Odyssey G5 34 inch

==================================================
  Price Comparison: Samsung Odyssey G5 34 inch
  Date: 2026-02-13
==================================================

  Platform Rankings (lowest first):
  1. Canada Computers: $399.99 CAD  << BEST DEAL
  2. BestBuy Canada: $449.99 CAD
  3. Amazon Canada: $479.99 CAD
  4. Newegg Canada: $499.99 CAD
  5. Memory Express: $519.99 CAD

  Price Trend: stable
==================================================
```

**Live mode** (with xAI key):
```
Shopping Sniper > find RTX 4070 prices across all platforms
```
The LLM agent autonomously searches, extracts prices, checks promotions, and presents a comparison table.

---

## Supported Platforms

| Platform | Domain | Scraping Method |
|----------|--------|-----------------|
| BestBuy Canada | bestbuy.ca | Snippet extraction (site blocks direct scraping) |
| Newegg Canada | newegg.ca | CSS selector: `li.price-current` |
| Canada Computers | canadacomputers.com | CSS selector: `span.sell-price` + JSON-LD |
| Memory Express | memoryexpress.com | CSS selector: `div.GrandTotal` |
| Amazon Canada | amazon.ca | Snippet extraction (bot protection) |

---

## Tool Reference

All tools use the LangChain `@tool` decorator and are registered to the agent automatically.

| Tool | Input | Description |
|------|-------|-------------|
| `search_product_prices` | Product name or SKU | Multi-platform DuckDuckGo search with per-site queries |
| `extract_price` | Search results JSON or URL | Hybrid extraction: snippet -> CSS -> JSON-LD -> regex |
| `check_promotions` | Date string (optional) | Check active/upcoming sales against promotion calendar |
| `build_task_prompt` | User query string | Parse intent (search/compare/track/alert) + extract threshold |
| `notify_price_alert` | Alert JSON | Push notification via Telegram and/or Email |
| `log_price_history` | Price entry JSON | Append to persistent price_log.json |
| `get_price_history` | Product name | Retrieve history + trend analysis (rising/falling/stable) |

---

## Testing

### Notification Test Suite

```bash
python test_notifier.py
```

```
==========================================================
  Shopping Sniper Agent -- Notifier Test Suite
==========================================================

  [ 1/12] test_build_alert_message_basic.............. PASS
  [ 2/12] test_build_alert_message_zero_savings....... PASS
  [ 3/12] test_build_alert_message_negative_savings... PASS
  [ 4/12] test_notify_sandbox_mode.................... PASS
  [ 5/12] test_notify_invalid_json.................... PASS
  [ 6/12] test_notify_missing_fields.................. PASS
  [ 7/12] test_notify_partial_fields.................. PASS
  [ 8/12] test_send_telegram_skipped_when_unconfigured PASS
  [ 9/12] test_send_email_skipped_when_unconfigured... PASS
  [10/12] test_live_telegram_if_configured............ SKIP
  [11/12] test_live_email_if_configured............... SKIP
  [12/12] test_live_full_pipeline_if_configured....... SKIP

  Results: 9 PASS | 0 FAIL | 3 SKIP | 0 ERROR
==========================================================
```

- **9 always-pass tests**: message formatting, sandbox mode, error handling, edge cases
- **3 conditional tests**: automatically run when notification credentials are configured

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Agent Framework | LangGraph `create_react_agent` (LangChain 1.2.x) |
| LLM Backend | Grok-3-mini via xAI API |
| Search Engine | DuckDuckGo (primary), Google Custom Search (fallback) |
| Web Scraping | BeautifulSoup4, Requests |
| Memory | LangGraph `MemorySaver` + `ChatMessageHistory` |
| Notifications | Telegram Bot API, SMTP (Gmail) |
| Configuration | python-dotenv, centralized config.py |

---

## Design Decisions

**Why DuckDuckGo over Google Custom Search?**
Google CSE requires a paid API key and has daily quota limits. DuckDuckGo is free and keyless, making the agent instantly runnable by anyone who clones the repo. Google CSE is kept as a fallback for users who want more consistent results.

**Why hybrid price extraction?**
Retailer websites vary wildly in structure and bot protection. Snippet regex is fast but unreliable. Direct scraping works for some sites but fails on others (BestBuy returns 403). The three-tier approach (snippet -> platform CSS -> JSON-LD -> generic regex) maximizes coverage while minimizing latency.

**Why dual sandbox/live mode?**
Every `@tool` function checks `config.is_sandbox()` and returns mock data when no real API keys are present. This means the full agent pipeline — search, extract, compare, notify — runs end-to-end without any external dependencies. Useful for development, testing, and demos.

**Why Grok instead of GPT-4 or Claude?**
Cost efficiency. Grok-3-mini via xAI provides strong tool-calling capabilities at a fraction of the cost of GPT-4o or Claude Sonnet, which is sufficient for a price comparison workflow that doesn't require complex reasoning.

---

## Known Limitations

This is a **demo / proof-of-concept** project, not a production system.

| Limitation | Production Solution |
|-----------|-------------------|
| DuckDuckGo results vary between runs | Paid search API (Serper.dev, Google CSE) |
| Some retailers block scraping (403) | Headless browser (Playwright), rotating proxies |
| No caching layer | Redis cache with TTL for repeated queries |
| Single-threaded search | Async workers, concurrent per-platform searches |
| Hardcoded promotion calendar | Scrape retailer promotion pages dynamically |
| Basic retry logic | Exponential backoff with circuit breakers |

---

## License

MIT
