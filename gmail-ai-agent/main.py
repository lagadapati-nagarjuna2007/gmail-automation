"""
main.py  –  Gmail AI Agent (Free Version — Railway Deploy)

Starts three things concurrently:
  1. FastAPI server       → /auth/login  /auth/callback  /health
  2. Telegram bot         → commands + auto-alerts
  3. Gmail polling loop   → checks inbox every 30 seconds
"""
import asyncio
import logging
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

telegram_app = build_telegram_app()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Gmail AI Agent starting...")

    # Start Telegram bot
    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.updater.start_polling(drop_pending_updates=True)
    logger.info("✅ Telegram bot started")

    # Start Gmail polling loop
    poll_task = asyncio.create_task(polling_loop())
    logger.info(f"✅ Gmail polling started (every {settings.poll_interval}s)")

    yield  # ← running

    # Graceful shutdown
    logger.info("Shutting down...")
    poll_task.cancel()
    await telegram_app.updater.stop()
    await telegram_app.stop()
    await telegram_app.shutdown()


app = FastAPI(
    title="Gmail AI Agent",
    description="24/7 AI Gmail monitor with Telegram alerts — free Railway deployment",
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
