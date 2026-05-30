"""
app/gmail/auth.py - FULLY FIXED timezone-aware datetime handling
"""
import logging
from datetime import datetime, timezone, timedelta
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from app.config import get_settings
from app.database.client import save_oauth_token, get_oauth_token

logger = logging.getLogger(__name__)
settings = get_settings()

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]

CLIENT_CONFIG = {
    "web": {
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uris": [settings.google_redirect_uri],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}


def _force_utc(dt: datetime) -> datetime:
    """
    Guarantee a datetime is timezone-aware UTC.
    - If already UTC-aware → return as-is
    - If aware but different tz → convert to UTC
    - If naive → assume UTC and attach tzinfo
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        # naive → assume UTC
        return dt.replace(tzinfo=timezone.utc)
    # aware → normalize to UTC
    return dt.astimezone(timezone.utc)


def _parse_expiry(expiry_str: str) -> datetime:
    """
    Parse any expiry string from DB and return timezone-aware UTC datetime.
    Handles: ISO format, Z suffix, +00:00 suffix, naive strings.
    """
    if not expiry_str:
        # Return a past time to force refresh
        return datetime(2000, 1, 1, tzinfo=timezone.utc)
    try:
        # Normalize Z → +00:00
        normalized = expiry_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        return _force_utc(dt)
    except Exception as e:
        logger.warning(f"Failed to parse expiry '{expiry_str}': {e} — forcing refresh")
        return datetime(2000, 1, 1, tzinfo=timezone.utc)


def _creds_to_dict(creds: Credentials) -> dict:
    """
    Serialize credentials to dict.
    Always store expiry as timezone-aware UTC ISO string.
    """
    expiry = None
    if creds.expiry:
        expiry = _force_utc(creds.expiry).isoformat()
    return {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "expiry": expiry,
    }


def get_auth_url() -> str:
    flow = Flow.from_client_config(
        CLIENT_CONFIG,
        scopes=SCOPES,
        redirect_uri=settings.google_redirect_uri,
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return auth_url


def exchange_code(code: str) -> dict:
    flow = Flow.from_client_config(
        CLIENT_CONFIG,
        scopes=SCOPES,
        redirect_uri=settings.google_redirect_uri,
    )
    flow.fetch_token(code=code)
    return _creds_to_dict(flow.credentials)


def get_credentials(user_email: str) -> Credentials | None:
    token_row = get_oauth_token(user_email)
    if not token_row:
        logger.warning(f"No OAuth token found for {user_email}")
        return None

    if not token_row.get("refresh_token"):
        logger.error(f"No refresh token for {user_email} — re-authentication required")
        return None

    # Build credentials object
    creds = Credentials(
        token=token_row["access_token"],
        refresh_token=token_row["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=SCOPES,
    )

    # Always set expiry as timezone-aware UTC
    creds.expiry = _parse_expiry(token_row.get("token_expiry", ""))

    # Check expiry manually to avoid Google's internal naive comparison bug
    now_utc = datetime.now(timezone.utc)
    is_expired = creds.expiry <= (now_utc + timedelta(seconds=60))  # 60s buffer

    if is_expired:
        logger.info(f"Token expired for {user_email}, refreshing...")
        try:
            creds.refresh(Request())
            # After refresh, Google sets creds.expiry as naive — fix it
            if creds.expiry and creds.expiry.tzinfo is None:
                creds.expiry = creds.expiry.replace(tzinfo=timezone.utc)
            save_oauth_token(user_email, _creds_to_dict(creds))
            logger.info(f"✅ Token refreshed for {user_email}")
        except Exception as e:
            logger.error(f"Token refresh failed for {user_email}: {e}")
            return None

    return creds
