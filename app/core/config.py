from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Ищем .env в корне проекта (два уровня вверх от app/core/).
_ENV_FILE = Path(__file__).parents[2] / ".env"


class Settings(BaseSettings):
    """Configuration settings for the application."""

    bot_token: SecretStr
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/tinvest"

    # Telegram ID администратора — единственный, кому доступна рассылка
    # /broadcast. Если не задан, рассылка отключена для всех.
    admin_id: int | None = None

    # Сервисный T-Invest токен для фоновых задач (синхронизация реестра эмитентов).
    t_invest_token: SecretStr | None = None

    # Базовый URL Cloud Run сервиса синхронизации облигаций пользователя
    bonds_sync_url: str | None = None

    # HTTP API для приёма событий от Cloud Tasks.
    api_host: str = "0.0.0.0"
    api_port: int = 8080

    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")


config = Settings()  # type: ignore
