"""
main.py - FIXED: single Telegram bot instance + clean event loop separation
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

# Singleton guard — prevents multiple bot instances
_bot_running = False
_bot_lock = threading.Lock()


def run_telegram_bot():
    """
    Telegram bot runs in its own OS thread with its own event loop.
    This fully isolates it from FastAPI's event loop — prevents Conflict errors.
    The singleton guard ensures only ONE instance ever starts.
    """
    global _bot_running

    with _bot_lock:
        if _bot_running:
            logger.warning("⚠️  Bot already running — blocked duplicate start")
            return
        _bot_running = True

    logger.info("Starting Telegram bot thread...")

    # Brand new event loop — completely isolated from FastAPI
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _bot_main():
        app = build_telegram_app()
        await app.initialize()
        await app.start()
        # drop_pending_updates=True prevents processing old queued messages
        await app.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
        )
        logger.info("✅ Telegram bot is polling")
        # Block forever — bot keeps running
        stop_event = asyncio.Event()
        await stop_event.wait()

    try:
        loop.run_until_complete(_bot_main())
    except Exception as e:
        logger.error(f"Telegram bot crashed: {e}")
    finally:
        with _bot_lock:
            _bot_running = False
        loop.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Gmail AI Agent starting...")

    # Start Telegram in its own thread — never touches FastAPI's event loop
    bot_thread = threading.Thread(
        target=run_telegram_bot,
        daemon=True,
        name="telegram-bot",
    )
    bot_thread.start()

    # Start Gmail polling in FastAPI's event loop
    poll_task = asyncio.create_task(polling_loop())
    logger.info(f"✅ Gmail polling started (every {settings.poll_interval}s)")

    yield  # App is running

    logger.info("Shutting down...")
    poll_task.cancel()
    try:
        await poll_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Gmail AI Agent",
    version="2.0.0",
    lifespan=lifespan,
)

app.include_router(router)

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", settings.app_port))
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=port,
        reload=False,
        log_level="info",
    )
