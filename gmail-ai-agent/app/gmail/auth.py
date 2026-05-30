"""
app/gmail/auth.py  –  Google OAuth 2.0 + credential management
FIXED: All datetime objects are timezone-aware UTC
"""
import logging
from datetime import datetime, timezone
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
    creds = flow.credentials
    return _creds_to_dict(creds)


def get_credentials(user_email: str) -> Credentials | None:
    token_row = get_oauth_token(user_email)
    if not token_row:
        logger.warning(f"No OAuth token for {user_email}")
        return None

    creds = Credentials(
        token=token_row["access_token"],
        refresh_token=token_row["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=SCOPES,
    )

    # FIX: Always set expiry as timezone-aware UTC datetime
    if token_row.get("token_expiry"):
        expiry_str = token_row["token_expiry"]
        try:
            expiry_str = expiry_str.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(expiry_str)
            # If naive (no tzinfo), force UTC
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            creds.expiry = parsed
        except Exception as e:
            logger.warning(f"Could not parse token_expiry: {e}")
            # Force refresh by setting expiry in the past
            creds.expiry = datetime(2000, 1, 1, tzinfo=timezone.utc)

    # Auto-refresh if expired
    try:
        if creds.expired and creds.refresh_token:
            logger.info(f"Refreshing token for {user_email}...")
            creds.refresh(Request())
            save_oauth_token(user_email, _creds_to_dict(creds))
            logger.info(f"Token refreshed for {user_email}")
    except Exception as e:
        logger.error(f"Token refresh failed for {user_email}: {e}")
        return None

    return creds


def _creds_to_dict(creds: Credentials) -> dict:
    """Always store expiry as timezone-aware UTC ISO string."""
    expiry = None
    if creds.expiry:
        if creds.expiry.tzinfo is None:
            expiry = creds.expiry.replace(tzinfo=timezone.utc).isoformat()
        else:
            expiry = creds.expiry.isoformat()
    return {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "expiry": expiry,
    }
