"""
Shopping Sniper Agent - Global Configuration
Reads all keys from .env with default fallbacks to prevent crashes.
"""
from dotenv import load_dotenv
import os

load_dotenv()

# ----- API Keys -----
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "TEST_GOOGLE_API_KEY_123456")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "TEST_CSE_ID_789012")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "TEST_GEMINI_API_KEY_345678")

# ----- Grok (xAI) -----
XAI_API_KEY = os.getenv("XAI_API_KEY", "")

# ----- Notification Config -----
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
NOTIFY_EMAIL_TO = os.getenv("NOTIFY_EMAIL_TO", "")

# ----- Target E-commerce Platforms -----
TARGET_PLATFORMS = [
    {"name": "BestBuy Canada", "domain": "bestbuy.ca"},
    {"name": "Newegg Canada", "domain": "newegg.ca"},
    {"name": "Canada Computers", "domain": "canadacomputers.com"},
    {"name": "Memory Express", "domain": "memoryexpress.com"},
    {"name": "Amazon Canada", "domain": "amazon.ca"},
]

# ----- Price Tracking Config -----
DEFAULT_MONITOR_DAYS = 30
PRICE_CHANGE_ALERT_THRESHOLD = 0.05  # Alert when price fluctuates more than 5%
PRICE_LOG_PATH = os.path.join(os.path.dirname(__file__), "data", "price_log.json")

# ----- Promotion Calendar -----
PROMOTION_EVENTS = [
    {"name": "Boxing Day", "month": 12, "day": 26},
    {"name": "Black Friday", "month": 11, "day_range": [24, 30]},
    {"name": "Cyber Monday", "month": 12, "day_range": [1, 3]},
    {"name": "Amazon Prime Day", "month": 7, "day_range": [10, 17]},
    {"name": "Back to School", "month": 8, "day_range": [15, 31]},
    {"name": "Canada Day Sale", "month": 7, "day": 1},
]

# ----- Sandbox Mode Detection -----
# Not sandbox if either Google API key or xAI key is real
SANDBOX_MODE = GOOGLE_API_KEY.startswith("TEST_") and not XAI_API_KEY

def is_sandbox():
    """Returns True when using test keys; tool modules should return mock data."""
    return SANDBOX_MODE
