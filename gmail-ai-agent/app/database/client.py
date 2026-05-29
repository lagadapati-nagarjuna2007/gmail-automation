"""
app/database/client.py  –  All Supabase DB operations
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from supabase import create_client, Client
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_supabase: Optional[Client] = None


def get_db() -> Client:
    global _supabase
    if _supabase is None:
        _supabase = create_client(settings.supabase_url, settings.supabase_key)
    return _supabase


# ── Users ────────────────────────────────────

def upsert_user(email: str, telegram_chat_id: str, name: str = "") -> dict:
    db = get_db()
    data = {
        "email": email,
        "telegram_chat_id": telegram_chat_id,
        "name": name,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    result = db.table("users").upsert(data, on_conflict="email").execute()
    return result.data[0] if result.data else {}


def get_all_users() -> list:
    db = get_db()
    return db.table("users").select("*").execute().data or []


def get_user_by_chat_id(chat_id: str) -> Optional[dict]:
    db = get_db()
    result = db.table("users").select("*").eq("telegram_chat_id", str(chat_id)).execute()
    return result.data[0] if result.data else None


# ── OAuth Tokens ─────────────────────────────

def save_oauth_token(user_email: str, token_data: dict) -> None:
    db = get_db()
    data = {
        "user_email": user_email,
        "access_token": token_data.get("access_token"),
        "refresh_token": token_data.get("refresh_token"),
        "token_expiry": token_data.get("expiry"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    db.table("oauth_tokens").upsert(data, on_conflict="user_email").execute()


def get_oauth_token(user_email: str) -> Optional[dict]:
    db = get_db()
    result = db.table("oauth_tokens").select("*").eq("user_email", user_email).execute()
    return result.data[0] if result.data else None


# ── Emails ───────────────────────────────────

def save_email(email_data: dict) -> dict:
    db = get_db()
    result = db.table("emails").upsert(email_data, on_conflict="message_id").execute()
    return result.data[0] if result.data else {}


def is_email_processed(message_id: str) -> bool:
    db = get_db()
    result = db.table("emails").select("id").eq("message_id", message_id).execute()
    return len(result.data) > 0


def get_recent_important_emails(limit: int = 10) -> list:
    db = get_db()
    result = (
        db.table("emails")
        .select("*")
        .eq("is_important", True)
        .order("received_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


def search_emails(query: str, limit: int = 8) -> list:
    db = get_db()
    result = (
        db.table("emails")
        .select("*")
        .or_(
            f"subject.ilike.%{query}%,"
            f"sender.ilike.%{query}%,"
            f"summary.ilike.%{query}%,"
            f"category.ilike.%{query}%"
        )
        .order("received_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


def get_emails_last_24h() -> list:
    db = get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    result = (
        db.table("emails")
        .select("*")
        .eq("is_important", True)
        .gte("received_at", cutoff)
        .order("received_at", desc=True)
        .execute()
    )
    return result.data or []


# ── Notifications ────────────────────────────

def save_notification(message_id: str, chat_id: str, telegram_msg_id: int) -> None:
    db = get_db()
    db.table("notifications").insert({
        "message_id": message_id,
        "telegram_chat_id": str(chat_id),
        "telegram_message_id": telegram_msg_id,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }).execute()


def notification_already_sent(message_id: str) -> bool:
    db = get_db()
    result = db.table("notifications").select("id").eq("message_id", message_id).execute()
    return len(result.data) > 0


# ── Groups ───────────────────────────────────

def get_group_emails(group_name: str) -> list[str]:
    db = get_db()
    group = db.table("groups").select("id").ilike("name", group_name).execute()
    if not group.data:
        return []
    group_id = group.data[0]["id"]
    members = db.table("group_members").select("email").eq("group_id", group_id).execute()
    return [m["email"] for m in (members.data or [])]


def list_groups() -> list:
    db = get_db()
    return db.table("groups").select("name").execute().data or []


# ── Stats ────────────────────────────────────

def get_stats() -> dict:
    db = get_db()
    total         = db.table("emails").select("id", count="exact").execute()
    important     = db.table("emails").select("id", count="exact").eq("is_important", True).execute()
    notifications = db.table("notifications").select("id", count="exact").execute()
    return {
        "total_emails_processed": total.count or 0,
        "important_emails": important.count or 0,
        "notifications_sent": notifications.count or 0,
    }
