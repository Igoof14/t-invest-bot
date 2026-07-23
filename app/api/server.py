"""Сборка и запуск aiohttp-сервера рядом с polling-циклом бота."""

from __future__ import annotations

import logging

from aiogram import Bot
from aiohttp import web
from core.config import config
from features.price_monitoring import api as price_monitoring_api

from .keys import BOT_KEY
from .middlewares import create_oidc_middleware

logger = logging.getLogger(__name__)

__all__ = ["BOT_KEY", "create_app", "start_api_server"]


async def handle_health(request: web.Request) -> web.Response:
    """Проверка живости сервиса (без аутентификации)."""
    return web.json_response({"status": "ok"})


def create_app(bot: Bot) -> web.Application:
    """Создаёт aiohttp-приложение и регистрирует роуты.

    Args:
        bot: Экземпляр aiogram-бота для отправки уведомлений.

    Returns:
        Готовое к запуску приложение.

    """
    app = web.Application(
        middlewares=[
            create_oidc_middleware(
                audience=config.api_audience,
                service_account_email=config.tasks_service_account_email,
            )
        ]
    )
    app[BOT_KEY] = bot
    app.router.add_get("/health", handle_health)
    app.add_routes(price_monitoring_api.routes)
    return app


async def start_api_server(bot: Bot, host: str, port: int) -> web.AppRunner:
    """Запускает HTTP-сервер в текущем event loop.

    Args:
        bot: Экземпляр aiogram-бота.
        host: Адрес для прослушивания.
        port: Порт для прослушивания.

    Returns:
        Запущенный AppRunner (держать ссылку до остановки процесса).

    """
    runner = web.AppRunner(create_app(bot))
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    logger.info("API-сервер запущен на %s:%d", host, port)
    return runner
