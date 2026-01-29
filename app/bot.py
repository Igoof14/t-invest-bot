import asyncio
import logging

from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore
from apscheduler.triggers.cron import CronTrigger  # type: ignore
from core.config import config
from core.database import db_manager
from core.enums import ReportType
from handlers.registration import register_handlers
from services.price_alert_service import PriceAlertService
from services.report_service import ReportService
from utils.bot_utils import BotUtils

logging.basicConfig(level=logging.INFO)

bot = Bot(token=config.bot_token.get_secret_value())
dp = Dispatcher()


async def main():
    """Start the bot."""
    await db_manager.create_tables()
    register_handlers(dp, bot)
    await BotUtils.set_commands(bot)
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

    scheduler.add_job(
        ReportService.send_report,
        CronTrigger(hour=18, minute=10, timezone="Europe/Moscow"),
        kwargs={"bot": bot, "report_type": ReportType.DAILY},
    )

    scheduler.add_job(
        ReportService.send_report,
        CronTrigger(day_of_week="fri", hour=18, minute=10, second=1, timezone="Europe/Moscow"),
        kwargs={"bot": bot, "report_type": ReportType.WEEKLY},
    )

    # Проверка аномалий цен облигаций каждый час в торговое время (10:00-18:00 МСК, пн-пт)
    scheduler.add_job(
        PriceAlertService.check_price_anomalies,
        CronTrigger(day_of_week="mon-fri", hour="10-18", minute=0, timezone="Europe/Moscow"),
        kwargs={"bot": bot},
    )

    scheduler.start()

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
