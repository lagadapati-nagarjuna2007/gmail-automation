"""
app/config.py  –  Central settings loaded from .env
"""
from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Google OAuth
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str

    # Telegram
    telegram_bot_token: str
    telegram_chat_id: str

    # Groq
    groq_api_key: str

    # Supabase
    supabase_url: str
    supabase_key: str

    # App
    app_host: str = "0.0.0.0"
    app_port: int = Field(default=8000, validation_alias=AliasChoices("PORT", "app_port"))
    app_base_url: str = "https://yourapp.up.railway.app"
    secret_key: str = "change_me"
    debug: bool = False

    # Polling
    poll_interval: int = 30  # seconds

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
