"""
Notifier Tool
Purpose: Send price drop alerts via Telegram and/or email.
Input: JSON string with product, price, platform, threshold, and URL.
Output: JSON string confirming notification status.
Dependencies: config (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, SMTP_*, is_sandbox)
"""
import json
from langchain.tools import tool

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import (
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    SMTP_EMAIL, SMTP_PASSWORD, SMTP_HOST, SMTP_PORT, NOTIFY_EMAIL_TO,
    is_sandbox,
)


def _send_telegram(message: str) -> dict:
    """Send a Telegram message using the Bot API."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return {"telegram": "skipped", "reason": "Token or chat ID not configured"}
    try:
        import requests
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return {"telegram": "sent"}
    except Exception as e:
        return {"telegram": "failed", "error": str(e)}


def _send_email(subject: str, body: str) -> dict:
    """Send an email notification via SMTP."""
    if not SMTP_EMAIL or not SMTP_PASSWORD or not NOTIFY_EMAIL_TO:
        return {"email": "skipped", "reason": "SMTP credentials or recipient not configured"}
    try:
        import smtplib
        from email.mime.text import MIMEText

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = SMTP_EMAIL
        msg["To"] = NOTIFY_EMAIL_TO

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, NOTIFY_EMAIL_TO, msg.as_string())
        return {"email": "sent"}
    except Exception as e:
        return {"email": "failed", "error": str(e)}


def _build_alert_message(product: str, price: float, platform: str,
                          threshold: float, url: str) -> str:
    """Build a formatted price alert message."""
    savings = threshold - price
    return (
        f"** Price Drop Alert! **\n\n"
        f"*Product:* {product}\n"
        f"*Current Price:* ${price:.2f} CAD\n"
        f"*Your Target:* ${threshold:.2f} CAD\n"
        f"*You Save:* ${savings:.2f} CAD\n"
        f"*Platform:* {platform}\n"
        f"*Link:* {url}\n\n"
        f"_Grab it before the price goes back up!_"
    )


@tool
def notify_price_alert(alert_json: str) -> str:
    """Send a price drop notification via Telegram and email.
    Input should be a JSON string with keys: product, price, platform, threshold, url.
    In sandbox mode, the notification is printed to console instead of sent."""
    try:
        data = json.loads(alert_json)
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid JSON input. Expected keys: product, price, platform, threshold, url."})

    product = data.get("product", "Unknown Product")
    price = float(data.get("price", 0))
    platform = data.get("platform", "Unknown")
    threshold = float(data.get("threshold", 0))
    url = data.get("url", "")

    message = _build_alert_message(product, price, platform, threshold, url)

    if is_sandbox():
        print(f"\n[SANDBOX NOTIFICATION]\n{message}\n")
        return json.dumps({
            "mode": "sandbox",
            "status": "printed_to_console",
            "product": product,
            "price": price,
            "threshold": threshold,
            "message_preview": message[:200],
        }, indent=2)

    telegram_result = _send_telegram(message)
    email_subject = f"Price Drop Alert: {product} at ${price:.2f} CAD"
    email_result = _send_email(email_subject, message.replace("*", "").replace("_", ""))

    return json.dumps({
        "mode": "live",
        "product": product,
        "price": price,
        "threshold": threshold,
        "telegram": telegram_result,
        "email": email_result,
    }, indent=2)
