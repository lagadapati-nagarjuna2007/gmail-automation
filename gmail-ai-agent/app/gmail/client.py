"""
app/gmail/client.py  –  All Gmail API operations
FIXED: All datetime objects are timezone-aware UTC
"""
import base64
import logging
import re
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.gmail.auth import get_credentials

logger = logging.getLogger(__name__)


def _service(user_email: str):
    creds = get_credentials(user_email)
    if not creds:
        raise RuntimeError(f"No valid credentials for {user_email}")
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


# ── Fetch new inbox message IDs ──────────────

def get_new_message_ids(user_email: str, since_history_id: Optional[str] = None) -> list[str]:
    try:
        svc = _service(user_email)

        if since_history_id:
            try:
                history = svc.users().history().list(
                    userId="me",
                    startHistoryId=since_history_id,
                    historyTypes=["messageAdded"],
                    labelId="INBOX",
                ).execute()
                ids = []
                for record in history.get("history", []):
                    for msg in record.get("messagesAdded", []):
                        ids.append(msg["message"]["id"])
                return ids
            except HttpError as e:
                if e.resp.status == 404:
                    logger.warning("History ID expired, falling back to recent fetch")
                else:
                    raise

        # Fallback: fetch last 10 unread inbox messages
        result = svc.users().messages().list(
            userId="me",
            labelIds=["INBOX", "UNREAD"],
            maxResults=10,
        ).execute()
        return [m["id"] for m in result.get("messages", [])]

    except HttpError as e:
        logger.error(f"Gmail list error for {user_email}: {e}")
        return []


def get_current_history_id(user_email: str) -> Optional[str]:
    try:
        svc = _service(user_email)
        profile = svc.users().getProfile(userId="me").execute()
        return str(profile.get("historyId", ""))
    except Exception as e:
        logger.error(f"Could not get historyId: {e}")
        return None


# ── Fetch a single message ───────────────────

def get_message(user_email: str, message_id: str) -> Optional[dict]:
    try:
        svc = _service(user_email)
        msg = svc.users().messages().get(
            userId="me", id=message_id, format="full"
        ).execute()
        return _parse_message(msg)
    except HttpError as e:
        logger.error(f"Gmail fetch error {message_id}: {e}")
        return None


def _parse_message(msg: dict) -> dict:
    headers = {
        h["name"].lower(): h["value"]
        for h in msg["payload"].get("headers", [])
    }

    sender_raw = headers.get("from", "")
    sender_name, sender_email = _parse_sender(sender_raw)
    subject = headers.get("subject", "(No Subject)")
    # FIX: always return timezone-aware datetime string
    received_at = _parse_date(headers.get("date", ""))
    body = _extract_body(msg["payload"])

    return {
        "message_id": msg["id"],
        "thread_id": msg.get("threadId", ""),
        "sender": sender_email,
        "sender_name": sender_name,
        "subject": subject,
        "body": body,
        "body_preview": body[:500] if body else "",
        "received_at": received_at,
        "has_attachments": _has_attachments(msg["payload"]),
        "labels": msg.get("labelIds", []),
    }


def _parse_sender(raw: str):
    match = re.match(r'^"?(.+?)"?\s*<(.+?)>$', raw.strip())
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return "", raw.strip()


def _parse_date(date_str: str) -> str:
    """Always return a timezone-aware ISO datetime string."""
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(date_str)
        # Ensure timezone-aware
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except Exception:
        # Always return timezone-aware UTC now as fallback
        return datetime.now(timezone.utc).isoformat()


def _extract_body(payload: dict) -> str:
    mime = payload.get("mimeType", "")

    if mime == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    if mime == "text/html":
        data = payload.get("body", {}).get("data", "")
        if data:
            html = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
            return _strip_html(html)

    for part in payload.get("parts", []):
        result = _extract_body(part)
        if result:
            return result
    return ""


def _strip_html(html: str) -> str:
    clean = re.sub(r'<[^>]+>', ' ', html)
    return re.sub(r'\s+', ' ', clean).strip()


def _has_attachments(payload: dict) -> bool:
    for part in payload.get("parts", []):
        if part.get("filename"):
            return True
        if _has_attachments(part):
            return True
    return False


# ── Send email ───────────────────────────────

def send_email(user_email: str, to: list[str], subject: str, body: str) -> bool:
    try:
        svc = _service(user_email)
        msg = MIMEMultipart("alternative")
        msg["From"] = user_email
        msg["To"] = ", ".join(to)
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        svc.users().messages().send(userId="me", body={"raw": raw}).execute()
        logger.info(f"Email sent → {to} | Subject: {subject}")
        return True
    except HttpError as e:
        logger.error(f"Send failed: {e}")
        return False


# ── Profile ──────────────────────────────────

def get_profile(user_email: str) -> dict:
    svc = _service(user_email)
    return svc.users().getProfile(userId="me").execute()
