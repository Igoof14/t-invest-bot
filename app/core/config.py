from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings for the application."""

    bot_token: SecretStr
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/tinvest"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


config = Settings()  # type: ignore
