"""Backend for frontend Telegram Mini App.

Мини-апп работает в браузере и не может ходить в бэкенд напрямую: тот принимает
``telegram_id`` прямо в пути и не проверяет вызывающего. Этот слой проверяет
подпись ``initData``, меняет её на сессию, подставляет пользователя сам и
переиспользует клиенты бэкенда, которыми уже пользуется меню бота.
"""

from .api import routes
from .auth import InitDataError, MiniAppUser, parse_init_data
from .middlewares import (
    auth_middleware,
    create_cors_middleware,
    current_user,
    no_store_middleware,
)
from .session import SessionError, issue_session, verify_session

__all__ = [
    "InitDataError",
    "MiniAppUser",
    "SessionError",
    "auth_middleware",
    "create_cors_middleware",
    "current_user",
    "issue_session",
    "no_store_middleware",
    "parse_init_data",
    "routes",
    "verify_session",
]
