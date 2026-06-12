from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Ищем .env в корне проекта (два уровня вверх от app/core/).
_ENV_FILE = Path(__file__).parents[2] / ".env"


class Settings(BaseSettings):
    """Configuration settings for the application."""

    bot_token: SecretStr
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/tinvest"

    # Сервисный T-Invest токен для фоновых задач (синхронизация реестра эмитентов).
    t_invest_token: SecretStr | None = None

    # API-ключ 2captcha для решения капч ФНС.
    captcha_api_key: str | None = None

    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")


config = Settings()  # type: ignore
