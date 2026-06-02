import asyncio
import logging

from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore
from apscheduler.triggers.cron import CronTrigger  # type: ignore
from common.utils.bot_utils import BotUtils
from core.config import config
from core.database import db_manager
from core.enums import ReportType
from features.base import base_handlers, notify_handlers
from features.coupons import coupon_handlers
from features.issuers import IssuerSyncService
from features.offer_warning import OfferAlertService
from features.offer_warning import handlers as offer_warning_handlers
from features.price_monitoring import PriceAlertService, price_alert_handlers
from features.reports import ReportService
from features.users import users_handlers

logging.basicConfig(level=logging.INFO)

bot = Bot(token=config.bot_token.get_secret_value())
dp = Dispatcher()


async def main():
    """Запуск бота."""
    await db_manager.create_tables()
    dp.include_routers(
        base_handlers.router,
        price_alert_handlers.router,
        offer_warning_handlers.router,
        notify_handlers.router,
        coupon_handlers.router,
        users_handlers.router,
    )

    # register_handlers(dp, bot)
    await BotUtils.set_commands(bot)
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

    scheduler.add_job(
        PriceAlertService.check_price_anomalies,
        CronTrigger(hour="10-20", minute=0, timezone="Europe/Moscow"),
        kwargs={"bot": bot},
    )

    # Дневная очистка старых записей цен и алертов (в ночь на 4:00 МСК).
    scheduler.add_job(
        PriceAlertService.run_daily_cleanup,
        CronTrigger(hour=4, minute=0, timezone="Europe/Moscow"),
        kwargs={"bot": bot},
    )

    # Ежедневный пересчёт уведомлений об офертах в 06:00 МСК
    scheduler.add_job(
        OfferAlertService.schedule_daily_jobs,
        CronTrigger(hour=6, minute=0, timezone="Europe/Moscow"),
        kwargs={"bot": bot, "scheduler": scheduler},
    )

    # Еженедельная синхронизация реестра эмитентов (каталог меняется медленно).
    scheduler.add_job(
        IssuerSyncService.sync_all_issuers,
        CronTrigger(day_of_week="sun", hour=5, minute=0, timezone="Europe/Moscow"),
    )

    scheduler.start()

    # Восстанавливаем DateTrigger-джобы после возможного рестарта
    await OfferAlertService.schedule_daily_jobs(bot, scheduler)

    # Разовый синк реестра эмитентов на старте (в фоне, не блокирует polling).
    scheduler.add_job(IssuerSyncService.sync_all_issuers)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
