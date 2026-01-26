"""Модуль для работы с хранилищем данных."""

from .alert_storage import AlertStorage
from .bot_user_storage import BotUserStorage

__all__ = ["AlertStorage", "BotUserStorage"]
