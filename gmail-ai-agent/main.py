"""
main.py  –  Gmail AI Agent (Fixed for Railway)
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


def run_telegram_bot():
    """Run Telegram bot in a separate thread with its own event loop."""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    telegram_app = build_telegram_app()

    async def start_bot():
        await telegram_app.initialize()
        await telegram_app.start()
        await telegram_app.updater.start_polling(drop_pending_updates=True)
        logger.info("✅ Telegram bot started")
        # Keep running forever
        await asyncio.Event().wait()

    loop.run_until_complete(start_bot())


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Gmail AI Agent starting...")

    # Start Telegram bot in separate thread
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    bot_thread.start()
    logger.info("✅ Telegram bot thread started")

    # Start Gmail polling loop
    poll_task = asyncio.create_task(polling_loop())
    logger.info(f"✅ Gmail polling started (every {settings.poll_interval}s)")

    yield

    # Shutdown
    poll_task.cancel()
    logger.info("Shutting down...")


app = FastAPI(
    title="Gmail AI Agent",
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