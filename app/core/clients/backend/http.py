"""HTTP-обвязка запросов к приватному Cloud Run сервису `backend`."""

import logging
from http import HTTPStatus
from typing import Any

import aiohttp
from core.config import config

from .auth import auth_headers
from .errors import BackendError, BackendNotConfigured, UserNotFound

logger = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=30)

# Ограничение эндпоинтов на количество возвращаемых элементов.
_MIN_LIMIT = 1
_MAX_LIMIT = 50


async def fetch_user_items(resource: str, telegram_id: int, limit: int) -> list[dict[str, Any]]:
    """Забирает `items` пользовательского ресурса бэкенда.

    Args:
        resource: Имя ресурса, например ``offers`` или ``maturities``.
        telegram_id: Telegram ID пользователя.
        limit: Сколько ближайших записей вернуть (1..50).

    Returns:
        Список сырых элементов ответа; пустой, если у пользователя их нет.

    Raises:
        BackendNotConfigured: Не задан `BACKEND_URL`.
        BackendAuthError: Не удалось получить OIDC id-token.
        UserNotFound: Бэкенд не знает такого пользователя.
        BackendError: Прочие ошибки запроса или разбора ответа.

    """
    base_url = config.backend_url
    if not base_url:
        raise BackendNotConfigured("BACKEND_URL не задан")

    base_url = base_url.rstrip("/")
    url = f"{base_url}/api/v1/users/{telegram_id}/{resource}"
    params = {"limit": max(_MIN_LIMIT, min(limit, _MAX_LIMIT))}
    headers = await auth_headers(base_url)

    try:
        async with (
            aiohttp.ClientSession(timeout=_TIMEOUT) as session,
            session.get(url, params=params, headers=headers) as resp,
        ):
            if resp.status == HTTPStatus.NOT_FOUND:
                raise UserNotFound(f"Пользователь {telegram_id} неизвестен бэкенду")
            resp.raise_for_status()
            payload = await resp.json()
    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
        raise BackendError(
            f"Ошибка запроса {resource} для пользователя {telegram_id}: {exc}"
        ) from exc

    return payload.get("items") or []
