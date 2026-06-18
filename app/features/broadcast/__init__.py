"""Админская рассылка сообщений всем пользователям."""

from .handlers import router
from .service import BroadcastService

__all__ = ["BroadcastService", "router"]
