from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr
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

    # Базовый URL приватного Cloud Run сервиса `backend` (оферты и т.д.), без пути.
    # Он же audience OIDC id-token'а, которым подписываются запросы к нему.
    backend_url: str | None = None

    # HTTP API для приёма событий от Cloud Tasks.
    # Порт берётся из PORT (его задаёт Cloud Run) или API_PORT; иначе 8080.
    api_host: str = "0.0.0.0"
    api_port: int = Field(
        default=8080,
        validation_alias=AliasChoices("PORT", "API_PORT"),
    )

    # OIDC-аутентификация запросов Cloud Tasks: ожидаемый audience (публичный
    # URL API) и email сервисного аккаунта, от имени которого приходят задачи.
    api_audience: str | None = None
    tasks_service_account_email: str | None = None

    # Webhook Telegram: публичный базовый URL сервиса, путь для приёма апдейтов
    # и secret token, который Telegram присылает в заголовке
    # ``X-Telegram-Bot-Api-Secret-Token`` для проверки подлинности запроса.
    webhook_base_url: str | None = None
    webhook_path: str = "/webhook"
    webhook_secret: SecretStr | None = None

    @property
    def webhook_url(self) -> str | None:
        """Полный URL webhook'а или ``None``, если базовый URL не задан."""
        if self.webhook_base_url is None:
            return None
        return self.webhook_base_url.rstrip("/") + "/" + self.webhook_path.lstrip("/")

    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")


config = Settings()  # type: ignore
