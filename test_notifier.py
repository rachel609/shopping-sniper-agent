"""
test_notifier.py
Purpose: Standalone test suite for the Shopping Sniper Agent notification system.
Tests sandbox mode, live mode (when configured), message formatting, and edge cases.
Usage: python test_notifier.py
Dependencies: tools/notifier.py, config.py
"""
import sys
import os
import json
import traceback

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.notifier import (
    _build_alert_message,
    _send_telegram,
    _send_email,
    notify_price_alert,
)
import tools.notifier as notifier_module
from config import (
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    SMTP_EMAIL, SMTP_PASSWORD, NOTIFY_EMAIL_TO,
    is_sandbox,
)


class SkipTest(Exception):
    """Raised to skip a test with a reason."""
    pass


# ============================================================
# Test Cases: Message Formatting
# ============================================================

def test_build_alert_message_basic():
    """Verify formatted message contains all expected fields."""
    msg = _build_alert_message(
        product="NVIDIA RTX 4070",
        price=549.99,
        platform="BestBuy Canada",
        threshold=599.99,
        url="https://bestbuy.ca/rtx4070"
    )
    assert "RTX 4070" in msg, "Product name missing from message"
    assert "$549.99" in msg, "Price missing from message"
    assert "$599.99" in msg, "Threshold missing from message"
    assert "$50.00" in msg, "Savings calculation incorrect (expected $50.00)"
    assert "BestBuy Canada" in msg, "Platform missing from message"
    assert "bestbuy.ca/rtx4070" in msg, "URL missing from message"
    assert "Price Drop Alert" in msg, "Alert header missing from message"


def test_build_alert_message_zero_savings():
    """Edge case: price equals threshold, savings should be $0.00."""
    msg = _build_alert_message("Test Product", 100.00, "Amazon", 100.00, "https://amazon.ca/test")
    assert "$0.00" in msg, "Zero savings not displayed correctly"


def test_build_alert_message_negative_savings():
    """Edge case: price above threshold, savings is negative."""
    msg = _build_alert_message("Test Product", 150.00, "Amazon", 100.00, "https://amazon.ca/test")
    # savings = 100 - 150 = -50, formatted as $-50.00
    assert "-50.00" in msg, "Negative savings not displayed correctly"


# ============================================================
# Test Cases: Sandbox Mode
# ============================================================

def test_notify_sandbox_mode():
    """Verify notify_price_alert returns sandbox JSON when is_sandbox() is True."""
    original_fn = notifier_module.is_sandbox
    try:
        notifier_module.is_sandbox = lambda: True

        alert_input = json.dumps({
            "product": "Sony WH-1000XM5",
            "price": 279.99,
            "platform": "Amazon Canada",
            "threshold": 350.00,
            "url": "https://amazon.ca/sony-xm5"
        })
        result_str = notify_price_alert.invoke(alert_input)
        result = json.loads(result_str)

        assert result["mode"] == "sandbox", f"Expected sandbox mode, got: {result['mode']}"
        assert result["status"] == "printed_to_console", f"Expected printed_to_console, got: {result['status']}"
        assert result["product"] == "Sony WH-1000XM5", f"Product mismatch: {result['product']}"
        assert result["price"] == 279.99, f"Price mismatch: {result['price']}"
        assert result["threshold"] == 350.00, f"Threshold mismatch: {result['threshold']}"
    finally:
        notifier_module.is_sandbox = original_fn


# ============================================================
# Test Cases: Error Handling
# ============================================================

def test_notify_invalid_json():
    """Verify notify_price_alert returns error on malformed JSON input."""
    result_str = notify_price_alert.invoke("this is not json {{{")
    result = json.loads(result_str)
    assert "error" in result, "Expected 'error' key in result"
    assert "Invalid JSON" in result["error"], f"Unexpected error message: {result['error']}"


def test_notify_missing_fields():
    """Verify notify_price_alert handles empty dict (all fields missing)."""
    original_fn = notifier_module.is_sandbox
    try:
        notifier_module.is_sandbox = lambda: True
        result_str = notify_price_alert.invoke(json.dumps({}))
        result = json.loads(result_str)

        assert result["mode"] == "sandbox", f"Expected sandbox mode, got: {result['mode']}"
        assert result["product"] == "Unknown Product", f"Expected default product, got: {result['product']}"
        assert result["price"] == 0.0, f"Expected default price 0.0, got: {result['price']}"
        assert result["threshold"] == 0.0, f"Expected default threshold 0.0, got: {result['threshold']}"
    finally:
        notifier_module.is_sandbox = original_fn


def test_notify_partial_fields():
    """Verify partial fields are handled, string price casts to float."""
    original_fn = notifier_module.is_sandbox
    try:
        notifier_module.is_sandbox = lambda: True
        result_str = notify_price_alert.invoke(json.dumps({
            "product": "Test GPU",
            "price": "499.99"
        }))
        result = json.loads(result_str)

        assert result["product"] == "Test GPU", f"Product mismatch: {result['product']}"
        assert result["price"] == 499.99, f"Price not cast from string: {result['price']}"
        assert result["threshold"] == 0.0, f"Threshold should default to 0.0: {result['threshold']}"
    finally:
        notifier_module.is_sandbox = original_fn


# ============================================================
# Test Cases: Channel Skip Behavior
# ============================================================

def test_send_telegram_skipped_when_unconfigured():
    """Verify _send_telegram returns 'skipped' when credentials are empty."""
    orig_token = notifier_module.TELEGRAM_BOT_TOKEN
    orig_chat = notifier_module.TELEGRAM_CHAT_ID
    try:
        notifier_module.TELEGRAM_BOT_TOKEN = ""
        notifier_module.TELEGRAM_CHAT_ID = ""

        result = _send_telegram("test message")
        assert result["telegram"] == "skipped", f"Expected 'skipped', got: {result['telegram']}"
        assert "not configured" in result.get("reason", ""), f"Unexpected reason: {result.get('reason')}"
    finally:
        notifier_module.TELEGRAM_BOT_TOKEN = orig_token
        notifier_module.TELEGRAM_CHAT_ID = orig_chat


def test_send_email_skipped_when_unconfigured():
    """Verify _send_email returns 'skipped' when credentials are empty."""
    orig_email = notifier_module.SMTP_EMAIL
    orig_pass = notifier_module.SMTP_PASSWORD
    orig_to = notifier_module.NOTIFY_EMAIL_TO
    try:
        notifier_module.SMTP_EMAIL = ""
        notifier_module.SMTP_PASSWORD = ""
        notifier_module.NOTIFY_EMAIL_TO = ""

        result = _send_email("Test Subject", "Test Body")
        assert result["email"] == "skipped", f"Expected 'skipped', got: {result['email']}"
        assert "not configured" in result.get("reason", ""), f"Unexpected reason: {result.get('reason')}"
    finally:
        notifier_module.SMTP_EMAIL = orig_email
        notifier_module.SMTP_PASSWORD = orig_pass
        notifier_module.NOTIFY_EMAIL_TO = orig_to


# ============================================================
# Test Cases: Live Mode (conditional -- SKIP if not configured)
# ============================================================

def test_live_telegram_if_configured():
    """Send a real Telegram message if credentials are present, otherwise SKIP."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise SkipTest("Telegram credentials not configured in .env")

    result = _send_telegram("[TEST] Shopping Sniper Agent - Notification test. Please ignore.")
    assert result["telegram"] == "sent", f"Telegram send failed: {result}"


def test_live_email_if_configured():
    """Send a real test email if SMTP credentials are present, otherwise SKIP."""
    if not SMTP_EMAIL or not SMTP_PASSWORD or not NOTIFY_EMAIL_TO:
        raise SkipTest("SMTP credentials not configured in .env")

    result = _send_email(
        "[TEST] Shopping Sniper Agent",
        "This is an automated test of the notification system.\n"
        "If you received this email, the SMTP notification channel is working correctly.\n\n"
        "-- Shopping Sniper Agent Test Suite"
    )
    assert result["email"] == "sent", f"Email send failed: {result}"


def test_live_full_pipeline_if_configured():
    """End-to-end notify_price_alert in live mode if any channel is configured."""
    if is_sandbox():
        raise SkipTest("Running in sandbox mode -- live pipeline test skipped")

    has_telegram = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)
    has_email = bool(SMTP_EMAIL and SMTP_PASSWORD and NOTIFY_EMAIL_TO)
    if not has_telegram and not has_email:
        raise SkipTest("No notification channels configured in .env")

    result_str = notify_price_alert.invoke(json.dumps({
        "product": "Test Product (Automated Test)",
        "price": 99.99,
        "platform": "Test Platform",
        "threshold": 120.00,
        "url": "https://example.com/test"
    }))
    result = json.loads(result_str)
    assert result["mode"] == "live", f"Expected live mode, got: {result['mode']}"

    # Verify at least one channel attempted (sent or skipped, not failed)
    if has_telegram:
        assert result["telegram"]["telegram"] != "failed", f"Telegram failed: {result['telegram']}"
    if has_email:
        assert result["email"]["email"] != "failed", f"Email failed: {result['email']}"


# ============================================================
# Test Runner
# ============================================================

def run_test(index, total, name, func):
    """Run a single test. Returns (name, status, detail)."""
    try:
        func()
        return (name, "PASS", "")
    except SkipTest as e:
        return (name, "SKIP", str(e))
    except AssertionError as e:
        return (name, "FAIL", str(e))
    except Exception as e:
        detail = f"{type(e).__name__}: {e}"
        return (name, "ERROR", detail)


def main():
    tests = [
        ("test_build_alert_message_basic", test_build_alert_message_basic),
        ("test_build_alert_message_zero_savings", test_build_alert_message_zero_savings),
        ("test_build_alert_message_negative_savings", test_build_alert_message_negative_savings),
        ("test_notify_sandbox_mode", test_notify_sandbox_mode),
        ("test_notify_invalid_json", test_notify_invalid_json),
        ("test_notify_missing_fields", test_notify_missing_fields),
        ("test_notify_partial_fields", test_notify_partial_fields),
        ("test_send_telegram_skipped_when_unconfigured", test_send_telegram_skipped_when_unconfigured),
        ("test_send_email_skipped_when_unconfigured", test_send_email_skipped_when_unconfigured),
        ("test_live_telegram_if_configured", test_live_telegram_if_configured),
        ("test_live_email_if_configured", test_live_email_if_configured),
        ("test_live_full_pipeline_if_configured", test_live_full_pipeline_if_configured),
    ]

    total = len(tests)
    results = []

    print("=" * 58)
    print("  Shopping Sniper Agent -- Notifier Test Suite")
    print("=" * 58)
    print()

    for i, (name, func) in enumerate(tests, 1):
        name_display, status, detail = run_test(i, total, name, func)
        results.append((name_display, status, detail))

        # Format line: [idx/total] name ........... STATUS
        idx_str = f"[{i:2d}/{total}]"
        # Pad name with dots to align status
        max_name_len = 48
        padded = name_display[:max_name_len].ljust(max_name_len, ".")
        status_str = status
        if detail:
            status_str = f"{status} ({detail})"

        print(f"  {idx_str} {padded} {status_str}")

    # Summary
    pass_count = sum(1 for _, s, _ in results if s == "PASS")
    fail_count = sum(1 for _, s, _ in results if s == "FAIL")
    skip_count = sum(1 for _, s, _ in results if s == "SKIP")
    error_count = sum(1 for _, s, _ in results if s == "ERROR")

    print()
    print("=" * 58)
    print(f"  Results: {pass_count} PASS | {fail_count} FAIL | {skip_count} SKIP | {error_count} ERROR")
    print("=" * 58)

    # Exit code: 0 if no failures/errors, 1 otherwise
    if fail_count > 0 or error_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
