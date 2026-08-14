"""HTTP-обвязка запросов к приватному Cloud Run сервису `backend`."""

import json as json_lib
import logging
from http import HTTPStatus
from typing import Any

import aiohttp
from core.config import config

from .auth import auth_headers
from .errors import (
    BackendError,
    BackendNotConfigured,
    InvalidToken,
    UpstreamUnavailable,
    UserNotFound,
)

logger = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=30)

# Ограничение эндпоинтов на количество возвращаемых элементов.
_MIN_LIMIT = 1
_MAX_LIMIT = 50

# `code` из тела ошибки бэкенда -> класс исключения. Всё, чего здесь нет,
# остаётся общим BackendError: вызывающему коду эти случаи неразличимы.
_ERROR_CODES: dict[str, type[BackendError]] = {
    "invalid_token": InvalidToken,
    "upstream_unavailable": UpstreamUnavailable,
}


def _error_from(body: str) -> type[BackendError]:
    """Класс исключения по телу ответа бэкенда.

    Бэкенд отдаёт ошибки как ``{"detail": ..., "code": ...}``, но полагаться на
    это нельзя: перед приложением стоит Cloud Run, и его собственные отказы
    приходят не в этом формате (а то и не JSON-ом вовсе).
    """
    try:
        payload = json_lib.loads(body)
    except ValueError:
        return BackendError
    if not isinstance(payload, dict):
        return BackendError
    code = payload.get("code")
    if not isinstance(code, str):
        return BackendError
    return _ERROR_CODES.get(code, BackendError)


def _base_url() -> str:
    """Базовый URL бэкенда без хвостового слэша.

    Raises:
        BackendNotConfigured: Не задан `BACKEND_URL`.

    """
    base_url = config.backend_url
    if not base_url:
        raise BackendNotConfigured("BACKEND_URL не задан")
    return base_url.rstrip("/")


async def request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Выполняет запрос к бэкенду и возвращает разобранный JSON.

    Args:
        method: HTTP-метод.
        path: Путь от корня сервиса, например ``/api/v1/users/register``.
        params: Query-параметры.
        json: Тело запроса.

    Returns:
        Тело ответа; для ``204 No Content`` — пустой словарь.

    Raises:
        BackendNotConfigured: Не задан `BACKEND_URL`.
        BackendAuthError: Не удалось получить OIDC id-token.
        UserNotFound: Бэкенд не знает такого пользователя.
        InvalidToken: T-Invest отверг токен.
        UpstreamUnavailable: Бэкенд не смог достучаться до T-Invest.
        BackendError: Прочие ошибки запроса или разбора ответа.

    """
    base_url = _base_url()
    headers = await auth_headers(base_url)

    try:
        async with (
            aiohttp.ClientSession(timeout=_TIMEOUT) as session,
            session.request(
                method, f"{base_url}{path}", params=params, json=json, headers=headers
            ) as resp,
        ):
            if resp.status == HTTPStatus.NOT_FOUND:
                raise UserNotFound(f"{method} {path}: пользователь неизвестен бэкенду")
            if resp.status >= HTTPStatus.BAD_REQUEST:
                # Тело ответа (`detail`/`code`) объясняет отказ лучше голого статуса,
                # а по `code` вызывающий код отличает «токен плохой» от «не смогли
                # проверить» — эти случаи требуют разных действий от пользователя.
                body = await resp.text()
                raise _error_from(body)(f"{method} {path} -> {resp.status}: {body}")
            if resp.status == HTTPStatus.NO_CONTENT:
                return {}
            return await resp.json()
    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
        raise BackendError(f"Ошибка запроса {method} {path}: {exc}") from exc


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
    payload = await request(
        "GET",
        f"/api/v1/users/{telegram_id}/{resource}",
        params={"limit": max(_MIN_LIMIT, min(limit, _MAX_LIMIT))},
    )
    return payload.get("items") or []
