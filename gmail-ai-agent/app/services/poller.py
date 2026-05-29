"""
app/services/poller.py  –  Gmail polling loop (replaces Pub/Sub)

Polls every POLL_INTERVAL seconds for new emails per registered user.
Uses Gmail historyId to efficiently detect only new messages.
"""
import asyncio
import logging
from datetime import datetime, timezone

from app.config import get_settings
from app.database.client import get_all_users, get_db
from app.gmail.client import get_new_message_ids, get_current_history_id, get_message
from app.ai.analyzer import analyze_email, is_important
from app.database.client import (
    save_email,
    is_email_processed,
    notification_already_sent,
)
from app.telegram.bot import send_alert_sync

logger = logging.getLogger(__name__)
settings = get_settings()

# In-memory store of last historyId per user
# { user_email: history_id_string }
_last_history_id: dict[str, str] = {}


async def polling_loop() -> None:
    """Main async loop — runs forever, polls Gmail every POLL_INTERVAL seconds."""
    logger.info(f"📡 Gmail polling started (every {settings.poll_interval}s)")

    # Initialize history IDs for all existing users
    await _init_history_ids()

    while True:
        try:
            await _poll_all_users()
        except Exception as e:
            logger.error(f"Polling loop error: {e}", exc_info=True)

        await asyncio.sleep(settings.poll_interval)


async def _init_history_ids() -> None:
    """Set baseline historyId for each user so we don't re-process old emails."""
    users = get_all_users()
    for user in users:
        email = user["email"]
        if email not in _last_history_id:
            history_id = get_current_history_id(email)
            if history_id:
                _last_history_id[email] = history_id
                logger.info(f"Baseline historyId set for {email}: {history_id}")


async def _poll_all_users() -> None:
    users = get_all_users()
    if not users:
        logger.debug("No users registered yet.")
        return

    for user in users:
        email = user["email"]
        try:
            await _poll_user(email)
        except Exception as e:
            logger.error(f"Poll error for {email}: {e}")


async def _poll_user(user_email: str) -> None:
    last_id = _last_history_id.get(user_email)
    message_ids = get_new_message_ids(user_email, since_history_id=last_id)

    if not message_ids:
        logger.debug(f"No new messages for {user_email}")
        # Update historyId even if no new messages
        new_id = get_current_history_id(user_email)
        if new_id:
            _last_history_id[user_email] = new_id
        return

    logger.info(f"Found {len(message_ids)} new message(s) for {user_email}")

    for msg_id in message_ids:
        _process_message(user_email, msg_id)

    # Update historyId after processing
    new_id = get_current_history_id(user_email)
    if new_id:
        _last_history_id[user_email] = new_id


def _process_message(user_email: str, message_id: str) -> None:
    """Full pipeline: fetch → AI analyze → save → alert."""

    # Duplicate guard
    if is_email_processed(message_id):
        logger.debug(f"Already processed: {message_id}")
        return

    # Fetch full message
    email_data = get_message(user_email, message_id)
    if not email_data:
        logger.warning(f"Could not fetch message {message_id}")
        return

    logger.info(f"Processing: '{email_data.get('subject', '')}' from {email_data.get('sender', '')}")

    # AI analysis
    analysis = analyze_email(
        subject=email_data.get("subject", ""),
        sender=email_data.get("sender", ""),
        sender_name=email_data.get("sender_name", ""),
        body=email_data.get("body", ""),
    )

    important = is_important(analysis)

    # Save to DB
    save_email({
        "message_id": message_id,
        "thread_id": email_data.get("thread_id", ""),
        "sender": email_data.get("sender", ""),
        "sender_name": email_data.get("sender_name", ""),
        "subject": email_data.get("subject", ""),
        "body_preview": email_data.get("body_preview", ""),
        "received_at": email_data.get("received_at", datetime.now(timezone.utc).isoformat()),
        "is_important": important,
        "importance_score": analysis.get("importance_score", 0),
        "urgency": analysis.get("urgency", "LOW"),
        "category": analysis.get("category", ""),
        "summary": analysis.get("summary", ""),
        "action_required": analysis.get("action_required", False),
        "reason": analysis.get("reason", ""),
        "deadline_detected": analysis.get("deadline_detected", False),
        "deadline": analysis.get("deadline"),
        "has_attachments": email_data.get("has_attachments", False),
        "labels": email_data.get("labels", []),
    })

    # Send Telegram alert only if important and not already notified
    if important and not notification_already_sent(message_id):
        logger.info(f"🔔 Sending alert | score={analysis.get('importance_score')} | {email_data.get('subject')}")
        send_alert_sync(email_data, analysis)
    else:
        logger.info(f"⏭️  Skipped (not important) | score={analysis.get('importance_score')} | {email_data.get('subject')}")


def register_new_user(user_email: str) -> None:
    """Called after OAuth — sets baseline historyId so we don't spam old emails."""
    history_id = get_current_history_id(user_email)
    if history_id:
        _last_history_id[user_email] = history_id
        logger.info(f"New user registered for polling: {user_email} (historyId={history_id})")
