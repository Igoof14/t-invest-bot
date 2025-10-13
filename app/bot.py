import asyncio
import logging

from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore
from apscheduler.triggers.cron import CronTrigger  # type: ignore
from core.config import config
from core.enums import ReportType
from handlers import base

logging.basicConfig(level=logging.INFO)

bot = Bot(token=config.bot_token.get_secret_value())
dp = Dispatcher()


async def main():
    """Start the bot."""
    base.register_handlers(dp, bot)
    await base.set_commands(bot)
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

    scheduler.add_job(
        base.send_report,
        CronTrigger(hour=18, minute=10),
        kwargs={"bot": bot, "report_type": ReportType.DAILY},
    )

    scheduler.add_job(
        base.send_report,
        CronTrigger(day_of_week="fri", hour=18, minute=10, second=1),
        kwargs={"bot": bot, "report_type": ReportType.WEEKLY},
    )
    scheduler.start()

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
