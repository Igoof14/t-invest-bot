"""Middleware мини-аппа: аутентификация и CORS.

Обе трогают только пути под ``/miniapp/`` — приём событий Cloud Tasks
(``/events/``) и webhook Telegram проходят мимо без изменений.

Подтвердиться можно двумя способами. ``Authorization: tma <initData>`` — подпись
Telegram, ею мини-апп пользуется один раз при входе. ``Authorization: Bearer
<token>`` — сессия, выданная в обмен на эту подпись; ею идут все остальные
запросы. Разделение нужно потому, что Telegram обновляет ``initData`` только при
запуске страницы, а мини-апп при закрытии не выгружается: см. ``session``.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from aiohttp import web
from core.config import config

from .auth import InitDataError, MiniAppUser, parse_init_data
from .session import SessionError, verify_session

logger = logging.getLogger(__name__)

_Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]

# Префикс, который защищает и обслуживает мини-апп.
PREFIX = "/miniapp/"

# Ключ запроса с подтверждённым пользователем.
USER_KEY = "miniapp_user"

_INIT_DATA_SCHEME = "tma "
_SESSION_SCHEME = "Bearer "


def _dev_user() -> MiniAppUser | None:
    """Пользователь для запуска фронтенда вне Telegram.

    Работает, только если ``MINIAPP_DEV_TELEGRAM_ID`` задан явно — в проде
    переменной нет, и запрос без подписи отклоняется.
    """
    if config.miniapp_dev_telegram_id is None:
        return None
    logger.warning(
        "Запрос мини-аппа без initData принят в дев-режиме как %s",
        config.miniapp_dev_telegram_id,
    )
    return MiniAppUser(telegram_id=config.miniapp_dev_telegram_id)


@web.middleware
async def no_store_middleware(request: web.Request, handler: _Handler) -> web.StreamResponse:
    """Запрещает кэширование ответов API.

    Ответы зависят от того, кто спрашивает, и меняются на каждое переключение
    тумблера. Без явного запрета их складывает у себя любой общий кэш на пути
    (Firebase Hosting раздаёт мини-апп через CDN) — и в худшем случае отдаёт
    настройки одного пользователя другому.
    """
    if not request.path.startswith(PREFIX):
        return await handler(request)

    try:
        response = await handler(request)
    except web.HTTPException as exc:
        # Отказы кэшировать тем более нельзя: протухший 404 или 401 переживёт
        # выкатку исправления и будет выглядеть как «ничего не починилось».
        exc.headers["Cache-Control"] = "no-store"
        raise

    response.headers["Cache-Control"] = "no-store"
    return response


@web.middleware
async def auth_middleware(request: web.Request, handler: _Handler) -> web.StreamResponse:
    """Пропускает запрос дальше, только если подпись Telegram или сессия сошлись."""
    if not request.path.startswith(PREFIX):
        return await handler(request)

    # Preflight приходит без заголовков авторизации — его обслуживает CORS.
    if request.method == "OPTIONS":
        return await handler(request)

    header = request.headers.get("Authorization", "")
    token = config.bot_token.get_secret_value()

    if header.startswith(_SESSION_SCHEME):
        try:
            user = verify_session(header.removeprefix(_SESSION_SCHEME), token)
        except SessionError as e:
            # Обычный конец жизни сессии, а не поломка: мини-апп в ответ на 401
            # сам обменяет подпись Telegram на новую.
            logger.info("Сессия мини-аппа не принята: %s", e)
            return web.json_response({"error": "invalid session"}, status=401)
    elif header.startswith(_INIT_DATA_SCHEME):
        try:
            user = parse_init_data(header.removeprefix(_INIT_DATA_SCHEME), token)
        except InitDataError as e:
            logger.warning("Отклонён запрос мини-аппа: %s", e)
            return web.json_response({"error": "invalid init data"}, status=401)
    else:
        dev_user = _dev_user()
        if dev_user is None:
            # Голый 401 в логе неотличим от «сломалось»: чаще всего это открытый
            # в обычном браузере фронтенд, которому не включили дев-режим.
            logger.warning(
                "%s без initData отклонён. Внутри Telegram подпись приходит сама; "
                "для обычного браузера задайте MINIAPP_DEV_TELEGRAM_ID",
                request.path,
            )
            return web.json_response({"error": "missing init data"}, status=401)
        user = dev_user

    request[USER_KEY] = user
    return await handler(request)


def create_cors_middleware(
    origin: str | None,
) -> Callable[[web.Request, _Handler], Awaitable[web.StreamResponse]]:
    """Создаёт CORS-middleware для статики мини-аппа на другом источнике.

    Нужна в разработке (Vite на другом порту) и когда фронтенд хостится
    отдельным доменом. Если источник не задан, заголовки не добавляются —
    открывать API всему интернету по умолчанию незачем.

    Args:
        origin: Разрешённый Origin, например ``http://localhost:5173``.

    Returns:
        aiohttp-middleware.

    """

    @web.middleware
    async def cors_middleware(request: web.Request, handler: _Handler) -> web.StreamResponse:
        if not origin or not request.path.startswith(PREFIX):
            return await handler(request)

        if request.method == "OPTIONS":
            response: web.StreamResponse = web.Response(status=204)
        else:
            try:
                response = await handler(request)
            except web.HTTPException as exc:
                # HTTPException — тоже ответ. Без этой ветки браузер увидел бы
                # вместо честного 400 непрозрачную CORS-ошибку.
                response = exc

        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Max-Age"] = "600"
        response.headers["Vary"] = "Origin"
        return response

    return cors_middleware


def current_user(request: web.Request) -> MiniAppUser:
    """Пользователь текущего запроса.

    Raises:
        KeyError: Обработчик вызван вне защищённого префикса — это ошибка
            конфигурации роутов, а не пользовательских данных.

    """
    return request[USER_KEY]
