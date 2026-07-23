import asyncio
import logging

from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore
from apscheduler.triggers.cron import CronTrigger  # type: ignore
from common.utils.bot_utils import BotUtils
from core.config import config
from core.database import db_manager
from core.enums import ReportType
from features.base import base_handlers
from features.broadcast import router as broadcast_router
from features.coupons import coupon_handlers
from features.fns_monitoring import router as fns_router
from features.fns_monitoring.menu import SECTION as fns_section
from features.menu import register_section
from features.menu import router as menu_router
from features.offer_warning import handlers as offer_warning_handlers
from features.offer_warning.menu import SECTION as offer_section
from features.onboarding import router as onboarding_router
from features.price_monitoring import price_alert_handlers
from features.price_monitoring.menu import SECTION as price_section
from features.ratings import router as ratings_router
from features.ratings.menu import SECTION as ratings_section
from features.reports import ReportService
from features.users import users_handlers

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
        base_handlers.router,
        broadcast_router,
        onboarding_router,
        price_alert_handlers.router,
        offer_warning_handlers.router,
        coupon_handlers.router,
        users_handlers.router,
        ratings_router,
        fns_router,
        menu_router,
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
