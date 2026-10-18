"""Notification package: Telegram summary of a syndication run.

Re-exported so callers use `notify.notify_telegram(...)` / `from core.notify
import notify_telegram`; implementation lives in telegram.py.
"""
from .telegram import notify_telegram, handle_webhook_update, auto_register_webhook, send_message

__all__ = ["notify_telegram", "handle_webhook_update", "auto_register_webhook", "send_message"]
