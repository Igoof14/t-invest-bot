"""Клиент бэкенда: пользователи бота.

Таблицей `bot_users` владеет бэкенд, поэтому бот ходит к ней только через эти
вызовы — своей модели пользователя у него больше нет.
"""

import logging
from dataclasses import dataclass

from common.brokers import Broker

from .http import request

logger = logging.getLogger(__name__)

_USERS = "/api/v1/users"


@dataclass
class Registration:
    """Состояние пользователя сразу после `/start`."""

    is_new_user: bool
    has_token: bool


async def register(
    telegram_id: int,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
) -> Registration:
    """Регистрирует пользователя или отмечает возвращение известного.

    Raises:
        BackendError: Ошибка конфигурации, авторизации или запроса.

    """
    payload = await request(
        "POST",
        f"{_USERS}/register",
        json={
            "telegram_id": telegram_id,
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
        },
    )
    return Registration(
        is_new_user=bool(payload.get("is_new_user")),
        has_token=bool(payload.get("has_token")),
    )


async def get_token(telegram_id: int, broker: Broker) -> str | None:
    """Read-only токен указанного брокера; None, если не подключён.

    Raises:
        UserNotFound: Бэкенд не знает такого пользователя.
        BackendError: Ошибка конфигурации, авторизации или запроса.

    """
    payload = await request("GET", f"{_USERS}/{telegram_id}/tokens/{broker.value}")
    return payload.get("token")


async def set_token(telegram_id: int, broker: Broker, token: str) -> None:
    """Сохраняет токен указанного брокера.

    Raises:
        UserNotFound: Бэкенд не знает такого пользователя.
        BackendError: Ошибка конфигурации, авторизации или запроса.

    """
    await request("PUT", f"{_USERS}/{telegram_id}/tokens/{broker.value}", json={"token": token})


async def delete_token(telegram_id: int, broker: Broker) -> None:
    """Отвязывает токен указанного брокера.

    Raises:
        UserNotFound: Бэкенд не знает такого пользователя.
        BackendError: Ошибка конфигурации, авторизации или запроса.

    """
    await request("DELETE", f"{_USERS}/{telegram_id}/tokens/{broker.value}")


async def has_any_token(telegram_id: int) -> bool:
    """Подключён ли у пользователя токен хоть одного брокера.

    Raises:
        UserNotFound: Бэкенд не знает такого пользователя.
        BackendError: Ошибка конфигурации, авторизации или запроса.

    """
    payload = await request("GET", f"{_USERS}/{telegram_id}/tokens")
    return bool(payload.get("has_token"))


async def deactivate(telegram_id: int) -> None:
    """Помечает пользователя неактивным — он заблокировал бота.

    Raises:
        UserNotFound: Бэкенд не знает такого пользователя.
        BackendError: Ошибка конфигурации, авторизации или запроса.

    """
    await request("POST", f"{_USERS}/{telegram_id}/deactivate")


async def list_active() -> list[int]:
    """Telegram ID всех активных пользователей — для рассылки.

    Raises:
        BackendError: Ошибка конфигурации, авторизации или запроса.

    """
    payload = await request("GET", f"{_USERS}/active")
    return list(payload.get("telegram_ids") or [])
