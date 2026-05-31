"""
app/api/routes.py  –  FastAPI routes
  GET /auth/login      → Start Google OAuth
  GET /auth/callback   → OAuth callback, save token, register user
  GET /health          → Health check
  GET /stats           → Processing stats
"""
import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from app.config import get_settings
from app.gmail.auth import get_auth_url, exchange_code, SCOPES
from app.database.client import upsert_user, save_oauth_token, get_stats
from app.services.poller import register_new_user

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()


# ── OAuth ─────────────────────────────────────

@router.get("/auth/login")
async def auth_login():
    """Redirect to Google OAuth consent screen."""
    url = get_auth_url()
    return RedirectResponse(url)


@router.get("/auth/callback")
async def auth_callback(code: str = Query(...), error: str = Query(None)):
    """Handle OAuth callback — save token, register user, start polling."""
    if error:
        raise HTTPException(400, detail=f"OAuth error: {error}")

    try:
        token_data = exchange_code(code)

        # Get Gmail address from token
        creds = Credentials(
            token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            scopes=SCOPES,
        )
        svc = build("gmail", "v1", credentials=creds, cache_discovery=False)
        profile = svc.users().getProfile(userId="me").execute()
        user_email = profile["emailAddress"]

       # Persist token + user
        upsert_user(
            email=user_email,
            telegram_chat_id=settings.telegram_chat_id,
            name=user_email.split("@")[0],
        )
        save_oauth_token(user_email, token_data)

        # Set baseline historyId so old emails are NOT re-processed
        register_new_user(user_email)

        logger.info(f"✅ OAuth complete for {user_email}")
        return HTMLResponse(content=_success_html(user_email))

    except Exception as e:
        logger.error(f"OAuth callback error: {e}", exc_info=True)
        raise HTTPException(500, detail=str(e))


# ── Health / Stats ────────────────────────────

@router.get("/health")
async def health():
    return {"status": "healthy", "service": "Gmail AI Agent"}

from fastapi import Response
@router.get("/ping")
@router.head("/ping")
async def ping():
    return {"status": "ok"}


@router.get("/stats")
async def stats():
    return get_stats()


# ── Success page ──────────────────────────────

def _success_html(email: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Gmail AI Agent – Connected</title>
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{
      font-family: system-ui, -apple-system, sans-serif;
      background: #0f172a;
      color: #f1f5f9;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    .card {{
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 20px;
      padding: 48px 40px;
      text-align: center;
      max-width: 440px;
      width: 90%;
    }}
    .icon {{ font-size: 56px; margin-bottom: 20px; }}
    h1 {{ font-size: 26px; color: #4ade80; margin-bottom: 10px; }}
    .email {{
      background: #0f172a;
      border-radius: 8px;
      padding: 10px 20px;
      font-family: monospace;
      color: #38bdf8;
      margin: 16px 0;
      display: inline-block;
    }}
    p {{ color: #94a3b8; line-height: 1.6; margin: 8px 0; }}
    .note {{ font-size: 13px; margin-top: 20px; color: #64748b; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">✅</div>
    <h1>Gmail Connected!</h1>
    <div class="email">{email}</div>
    <p>Your AI assistant is now monitoring this inbox.</p>
    <p>You will receive <strong>automatic Telegram alerts</strong><br>whenever important emails arrive.</p>
    <p class="note">You can close this window.</p>
  </div>
</body>
</html>"""
