import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

from app.invest import get_payment

_ = load_dotenv(".env")
TOKEN = str(os.environ.get("bot_token"))

bot = Bot(token=TOKEN)
dp = Dispatcher()

user_ids: set[int] = set()


@dp.message(Command("start"))
async def start_handler(message: Message):
    """обработка /start."""
    user_ids.add(message.chat.id)
    _ = await message.answer(text="Привет! Я Bondelo, делюсь информациец о облигациях")


@dp.message(Command("report"))
async def start_handler(message: Message):
    """обработка /report."""
    _ = await message.answer(get_payment(), parse_mode="HTML")


async def send_daily_report():
    """рассылка отчёта."""
    if not user_ids:
        return

    text = get_payment()
    for uid in user_ids:
        try:
            await bot.send_message(uid, text, parse_mode="HTML")
        except Exception as e:
            print(f"❌ ошибка при отправке {uid}: {e}")


async def main():
    """Start the bot."""
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    _ = scheduler.add_job(send_daily_report, CronTrigger(hour=16, minute=42))
    scheduler.start()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
