"""
app/telegram/bot.py  –  Telegram bot: automatic alerts + commands + email sending
"""
import asyncio
import logging
import re

from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode

from app.config import get_settings
from app.database import client as db
from app.gmail.client import send_email

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Auto Alert (called from polling pipeline) ─

async def send_important_alert(email_data: dict, analysis: dict) -> None:
    """Push automatic Telegram notification for an important email."""
    bot = Bot(token=settings.telegram_bot_token)
    chat_id = settings.telegram_chat_id

    urgency_emoji = {"CRITICAL": "🚨", "HIGH": "⚠️", "MEDIUM": "📌", "LOW": "📧"}.get(
        analysis.get("urgency", "LOW"), "📧"
    )
    action = "✅ *Action Required*" if analysis.get("action_required") else "ℹ️ No action needed"
    deadline = (
        f"\n⏰ *Deadline:* {analysis['deadline']}"
        if analysis.get("deadline_detected") and analysis.get("deadline")
        else ""
    )

    text = (
        f"{urgency_emoji} *IMPORTANT EMAIL*\n"
        f"{'─' * 28}\n"
        f"📂 *Category:* {analysis.get('category', 'General')}\n"
        f"📨 *From:* {email_data.get('sender_name') or email_data.get('sender', 'Unknown')}\n"
        f"📝 *Subject:* {_esc(email_data.get('subject', '(No Subject)'))}\n\n"
        f"📋 *Summary:*\n{_esc(analysis.get('summary', ''))}\n\n"
        f"{action}\n"
        f"🎯 *Score:* {analysis.get('importance_score', 0)}/100\n"
        f"⚡ *Urgency:* {analysis.get('urgency', 'LOW')}\n"
        f"💡 *Reason:* {_esc(analysis.get('reason', ''))}"
        f"{deadline}"
    )

    try:
        sent = await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
        )
        db.save_notification(email_data["message_id"], str(chat_id), sent.message_id)
        logger.info(f"✅ Telegram alert sent for {email_data['message_id']}")
    except Exception as e:
        logger.error(f"Telegram alert failed: {e}")


def send_alert_sync(email_data: dict, analysis: dict) -> None:
    """Sync wrapper — called from the polling thread."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(send_important_alert(email_data, analysis))
        else:
            loop.run_until_complete(send_important_alert(email_data, analysis))
    except RuntimeError:
        asyncio.run(send_important_alert(email_data, analysis))


def _esc(text: str) -> str:
    """Escape special Markdown characters."""
    for ch in r"_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, f"\\{ch}")
    return text


# ── Commands ──────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Gmail AI Agent is active\\!*\n\n"
        "I monitor your Gmail every 30 seconds and alert you automatically when important emails arrive\\.\n\n"
        "You don't need to open Gmail ever again\\.\n\n"
        "Type /help to see all commands\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Commands*\n\n"
        "/inbox — Last 10 important emails\n"
        "/search \\<query\\> — Search emails\n"
        "/summarize — Last 24h summary\n"
        "/stats — Processing stats\n"
        "/groups — Contact groups\n\n"
        "📨 *Send Email \\(just type\\):*\n"
        "`Send email to john@gmail.com`\n"
        "`Subject: Meeting tomorrow`\n"
        "`Let's meet at 10 AM.`\n\n"
        "Or to a group:\n"
        "`Send email to Recruiters`\n"
        "`Subject: Application Update`\n"
        "`Body here...`",
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def cmd_inbox(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    emails = db.get_recent_important_emails(limit=10)
    if not emails:
        await update.message.reply_text("📭 No important emails yet.")
        return
    lines = ["📬 *Recent Important Emails*\n"]
    for i, e in enumerate(emails, 1):
        lines.append(
            f"{i}\\. *{_esc(e.get('subject', '(No Subject)'))}*\n"
            f"   From: {_esc(e.get('sender', 'Unknown'))}\n"
            f"   Score: {e.get('importance_score', 0)}/100 \\| {_esc(e.get('category', ''))}\n"
        )
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2)


async def cmd_search(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = " ".join(ctx.args).strip()
    if not query:
        await update.message.reply_text("Usage: /search interview")
        return
    emails = db.search_emails(query)
    if not emails:
        await update.message.reply_text(f"🔍 No emails found for: {query}")
        return
    lines = [f"🔍 *Results for '{_esc(query)}'*\n"]
    for i, e in enumerate(emails, 1):
        summary = e.get("summary", "")[:100]
        lines.append(
            f"{i}\\. *{_esc(e.get('subject', ''))}*\n"
            f"   {_esc(summary)}\\.\\.\\.\n"
        )
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2)


async def cmd_summarize(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    emails = db.get_emails_last_24h()
    if not emails:
        await update.message.reply_text("📭 No important emails in the last 24 hours.")
        return
    lines = [f"📊 *Daily Summary — {len(emails)} important emails*\n"]
    for i, e in enumerate(emails, 1):
        lines.append(
            f"{i}\\. *{_esc(e.get('subject', ''))}*\n"
            f"   {_esc(e.get('summary', '')[:100])}\\.\\.\\.\n"
            f"   Score: {e.get('importance_score', 0)}/100\n"
        )
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2)


async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    s = db.get_stats()
    await update.message.reply_text(
        f"📊 *Agent Stats*\n\n"
        f"Emails processed: {s['total_emails_processed']}\n"
        f"Important emails: {s['important_emails']}\n"
        f"Notifications sent: {s['notifications_sent']}",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_groups(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    groups = db.list_groups()
    if not groups:
        await update.message.reply_text("No contact groups found. Add them via Supabase.")
        return
    names = "\n".join(f"• {g['name']}" for g in groups)
    await update.message.reply_text(f"📋 *Contact Groups*\n\n{names}", parse_mode=ParseMode.MARKDOWN)


# ── Natural language email send ───────────────

_send_state: dict = {}  # chat_id → state


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    if chat_id in _send_state:
        await _continue_send(update, ctx, text)
        return

    if text.lower().startswith(("send email", "send mail")):
        await _start_send(update, ctx, text)
        return

    if text.lower().startswith("search "):
        ctx.args = text[7:].split()
        await cmd_search(update, ctx)
        return

    await update.message.reply_text("Type /help to see available commands.")


async def _start_send(update: Update, ctx: ContextTypes.DEFAULT_TYPE, text: str):
    chat_id = update.effective_chat.id
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    recipients = _extract_recipients(lines[0])
    if not recipients:
        await update.message.reply_text(
            "❓ Could not find recipients.\n\nExamples:\n"
            "Send email to john@gmail.com\n"
            "Send email to Recruiters"
        )
        return

    subject = ""
    body_lines = []
    reading_body = False

    for line in lines[1:]:
        low = line.lower()
        if low.startswith("subject:"):
            subject = line[8:].strip()
        elif low == "body:" or reading_body:
            reading_body = True
            if low != "body:":
                body_lines.append(line)
        else:
            body_lines.append(line)

    body = "\n".join(body_lines).strip()

    if not subject:
        _send_state[chat_id] = {"recipients": recipients, "step": "subject"}
        await update.message.reply_text(
            f"📨 To: {', '.join(recipients)}\n\n✏️ Enter the email subject:"
        )
        return

    if not body:
        _send_state[chat_id] = {"recipients": recipients, "subject": subject, "step": "body"}
        await update.message.reply_text("✏️ Enter the email body:")
        return

    await _confirm_or_send(update, ctx, recipients, subject, body)


async def _continue_send(update: Update, ctx: ContextTypes.DEFAULT_TYPE, text: str):
    chat_id = update.effective_chat.id
    state = _send_state[chat_id]

    if state["step"] == "subject":
        state["subject"] = text
        state["step"] = "body"
        await update.message.reply_text("✏️ Enter the email body:")

    elif state["step"] == "body":
        state["body"] = text
        del _send_state[chat_id]
        await _confirm_or_send(update, ctx, state["recipients"], state["subject"], state["body"])

    elif state["step"] == "confirm":
        if text.strip().upper() == "YES":
            r, s, b = state["recipients"], state["subject"], state["body"]
            del _send_state[chat_id]
            await _do_send(update, r, s, b)
        else:
            del _send_state[chat_id]
            await update.message.reply_text("❌ Email cancelled.")


async def _confirm_or_send(update, ctx, recipients, subject, body):
    chat_id = update.effective_chat.id
    if len(recipients) > 5:
        _send_state[chat_id] = {
            "step": "confirm",
            "recipients": recipients,
            "subject": subject,
            "body": body,
        }
        await update.message.reply_text(
            f"⚠️ *Confirm Send*\n\n"
            f"Recipients: *{len(recipients)}*\n"
            f"Subject: *{subject}*\n\n"
            f"Reply *YES* to send to all {len(recipients)} recipients.",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await _do_send(update, recipients, subject, body)


async def _do_send(update, recipients, subject, body):
    user = db.get_user_by_chat_id(str(update.effective_chat.id))
    if not user:
        await update.message.reply_text("❌ No Gmail linked. Visit /auth/login first.")
        return

    ok = send_email(user["email"], recipients, subject, body)
    if ok:
        await update.message.reply_text(
            f"✅ *Email sent!*\n\nTo: {', '.join(recipients)}\nSubject: {subject}",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await update.message.reply_text("❌ Failed to send. Please try again.")


def _extract_recipients(text: str) -> list[str]:
    emails = re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)
    if emails:
        return emails
    # Try group name
    clean = re.sub(r"(?i)send (email|mail) to\s*", "", text).strip()
    if clean:
        group_emails = db.get_group_emails(clean)
        if group_emails:
            return group_emails
    return []


# ── Build app ────────────────────────────────

def build_telegram_app() -> Application:
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("inbox", cmd_inbox))
    app.add_handler(CommandHandler("show_important", cmd_inbox))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CommandHandler("summarize", cmd_summarize))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("groups", cmd_groups))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app
