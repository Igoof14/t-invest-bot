"""HTTP API для приёма событий от внешних сервисов (Google Cloud Tasks)."""

from .server import create_app

__all__ = ["create_app"]
