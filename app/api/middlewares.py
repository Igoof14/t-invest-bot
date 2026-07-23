"""Middleware аутентификации входящих запросов от Google Cloud Tasks."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from aiohttp import web
from google.auth.transport.requests import Request
from google.oauth2 import id_token as google_id_token

logger = logging.getLogger(__name__)

_Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]

# Пути, защищённые OIDC-аутентификацией.
_PROTECTED_PREFIX = "/events/"


def _verify_token(token: str, audience: str) -> Mapping[str, Any]:
    """Проверяет OIDC id-token (блокирующий вызов — ходит за сертификатами)."""
    return google_id_token.verify_oauth2_token(token, Request(), audience)


def create_oidc_middleware(
    audience: str | None,
    service_account_email: str | None,
) -> Callable[[web.Request, _Handler], Awaitable[web.StreamResponse]]:
    """Создаёт middleware проверки OIDC-токена Cloud Tasks.

    Args:
        audience: Ожидаемый ``aud`` токена (публичный URL API).
        service_account_email: Email сервисного аккаунта Cloud Tasks.

    Returns:
        aiohttp-middleware. Если параметры не заданы, все защищённые
        запросы отклоняются с 503.

    """

    @web.middleware
    async def oidc_middleware(
        request: web.Request, handler: _Handler
    ) -> web.StreamResponse:
        if not request.path.startswith(_PROTECTED_PREFIX):
            return await handler(request)

        if not audience or not service_account_email:
            logger.error("OIDC-аутентификация не настроена — запрос отклонён")
            return web.json_response({"error": "auth is not configured"}, status=503)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return web.json_response({"error": "missing bearer token"}, status=401)

        token = auth_header.removeprefix("Bearer ")
        try:
            claims = await asyncio.to_thread(_verify_token, token, audience)
        except ValueError as e:
            logger.warning("Невалидный OIDC-токен: %s", e)
            return web.json_response({"error": "invalid token"}, status=401)

        if claims.get("email") != service_account_email or not claims.get(
            "email_verified"
        ):
            logger.warning(
                "OIDC-токен от неожиданного аккаунта: %s", claims.get("email")
            )
            return web.json_response({"error": "forbidden"}, status=403)

        return await handler(request)

    return oidc_middleware
