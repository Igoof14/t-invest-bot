"""Сборка aiohttp-сервера: webhook Telegram и события внешних сервисов."""

from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from core.config import config
from features.disclosure import api as disclosure_api
from features.fns_monitoring import api as fns_monitoring_api
from features.offer_warning import api as offer_warning_api
from features.price_monitoring import api as price_monitoring_api
from features.ratings import api as ratings_api

from .keys import BOT_KEY
from .middlewares import create_oidc_middleware

__all__ = ["BOT_KEY", "create_app"]


async def handle_health(request: web.Request) -> web.Response:
    """Проверка живости сервиса (без аутентификации)."""
    return web.json_response({"status": "ok"})


def create_app(bot: Bot, dp: Dispatcher) -> web.Application:
    """Создаёт aiohttp-приложение и регистрирует роуты.

    Args:
        bot: Экземпляр aiogram-бота для отправки уведомлений.
        dp: Диспетчер aiogram для обработки webhook-апдейтов Telegram.

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
    app.add_routes(offer_warning_api.routes)
    app.add_routes(fns_monitoring_api.routes)
    app.add_routes(ratings_api.routes)
    app.add_routes(disclosure_api.routes)

    secret = config.webhook_secret.get_secret_value() if config.webhook_secret else None
    SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=secret).register(
        app, path=config.webhook_path
    )
    setup_application(app, dp, bot=bot)
    return app
