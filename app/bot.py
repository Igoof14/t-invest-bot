import asyncio
import logging

from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore
from apscheduler.triggers.cron import CronTrigger  # type: ignore
from common.utils.bot_utils import BotUtils
from core.config import config
from core.database import db_manager
from core.enums import ReportType
from features import (
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
from features.reports import ReportService

logging.basicConfig(level=logging.INFO)

bot = Bot(token=config.bot_token.get_secret_value())
dp = Dispatcher()

# Удержание фоновых объектов/задач на время жизни процесса (защита от GC).
_BACKGROUND: list[object] = []


async def main():
    """Запуск бота."""
    await db_manager.create_tables()

    # Регистрируем секции хаба «Уведомления» (порядок = порядок в меню).
    register_section(price_section)
    register_section(offer_section)
    register_section(ratings_section)
    register_section(fns_section)

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

    await BotUtils.set_commands(bot)
    await BotUtils.set_descriptions(bot)
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

    scheduler.add_job(
        ReportService.send_report,
        CronTrigger(day_of_week="mon-fri", hour=18, minute=10, timezone="Europe/Moscow"),
        kwargs={"bot": bot, "report_type": ReportType.DAILY},
    )

    scheduler.add_job(
        ReportService.send_report,
        CronTrigger(day_of_week="fri", hour=18, minute=10, second=1, timezone="Europe/Moscow"),
        kwargs={"bot": bot, "report_type": ReportType.WEEKLY},
    )

    scheduler.start()

    # Восстанавливаем DateTrigger-джобы после возможного рестарта

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
