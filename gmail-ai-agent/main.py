"""
main.py  –  Gmail AI Agent
FIXED: Telegram bot runs in separate thread to avoid event loop conflicts
"""
import asyncio
import logging
import threading
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from app.logger import setup_logging
from app.config import get_settings
from app.api.routes import router
from app.telegram.bot import build_telegram_app
from app.services.poller import polling_loop

settings = get_settings()
setup_logging(debug=settings.debug)
logger = logging.getLogger(__name__)

# Global flag to prevent multiple bot instances
_bot_started = False
_bot_lock = threading.Lock()


def run_telegram_bot():
    """
    Run Telegram bot in a completely separate thread with its own event loop.
    This prevents the Conflict error caused by two polling instances.
    """
    global _bot_started

    with _bot_lock:
        if _bot_started:
            logger.warning("Bot already started — skipping duplicate instance")
            return
        _bot_started = True

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    telegram_app = build_telegram_app()

    async def _run():
        await telegram_app.initialize()
        await telegram_app.start()
        await telegram_app.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
        )
        logger.info("✅ Telegram bot polling started")
        # Keep alive forever
        await asyncio.Event().wait()

    try:
        loop.run_until_complete(_run())
    except Exception as e:
        logger.error(f"Telegram bot error: {e}")
    finally:
        _bot_started = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Gmail AI Agent starting...")

    # Start Telegram bot in its own thread
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True, name="telegram-bot")
    bot_thread.start()
    logger.info("✅ Telegram bot thread launched")

    # Start Gmail polling loop in async task
    poll_task = asyncio.create_task(polling_loop())
    logger.info(f"✅ Gmail polling started (every {settings.poll_interval}s)")

    yield  # App is running

    # Graceful shutdown
    logger.info("Shutting down Gmail AI Agent...")
    poll_task.cancel()
    try:
        await poll_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Gmail AI Agent",
    description="24/7 AI Gmail monitor with Telegram alerts",
    version="2.0.0",
    lifespan=lifespan,
)

app.include_router(router)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
        log_level="info",
    )
