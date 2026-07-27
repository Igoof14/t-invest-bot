import logging

from aiogram import Bot, Dispatcher
from aiohttp import web
from api import create_app
from common.utils.bot_utils import BotUtils
from core.config import config
from core.database import db_manager
from features import (
    analytics,
    base,
    broadcast,
    coupons,
    fns_monitoring,
    offer_warning,
    onboarding,
    price_monitoring,
    ratings,
    users,
)
from features import menu as menu_feature
from features.fns_monitoring.menu import SECTION as fns_section
from features.menu import register_section
from features.offer_warning.menu import SECTION as offer_section
from features.price_monitoring.menu import SECTION as price_section
from features.ratings.menu import SECTION as ratings_section

logging.basicConfig(level=logging.INFO)

bot = Bot(token=config.bot_token.get_secret_value())
dp = Dispatcher()


async def on_startup(bot: Bot) -> None:
    """Готовит сервис и регистрирует webhook Telegram.

    Args:
        bot: Экземпляр aiogram-бота (внедряется диспетчером).

    Raises:
        RuntimeError: Если публичный URL webhook'а не сконфигурирован.

    """
    await db_manager.create_tables()
    await BotUtils.set_commands(bot)
    await BotUtils.set_descriptions(bot)

    if config.webhook_url is None:
        raise RuntimeError("webhook_base_url is not configured")

    secret = config.webhook_secret.get_secret_value() if config.webhook_secret else None
    await bot.set_webhook(
        url=config.webhook_url,
        secret_token=secret,
        allowed_updates=dp.resolve_used_update_types(),
        drop_pending_updates=True,
    )


def main() -> None:
    """Собирает приложение и запускает webhook-сервер."""
    # Регистрируем секции хаба «Уведомления» (порядок = порядок в меню).
    register_section(price_section)
    register_section(offer_section)
    register_section(ratings_section)
    register_section(fns_section)

    # Продуктовая аналитика: outer-мидлварь на update видит каждый апдейт
    # ровно один раз, включая те, для которых не нашлось хендлера.
    dp.update.outer_middleware(analytics.AnalyticsMiddleware())

    dp.include_routers(
        base.router,
        broadcast.router,
        onboarding.router,
        price_monitoring.router,
        offer_warning.router,
        coupons.router,
        users.router,
        ratings.router,
        fns_monitoring.router,
        menu_feature.router,
    )

    dp.startup.register(on_startup)

    app = create_app(bot, dp)
    web.run_app(app, host=config.api_host, port=config.api_port)


if __name__ == "__main__":
    main()
