import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import BotCommand, KeyboardButton, Message, ReplyKeyboardMarkup
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore
from apscheduler.triggers.cron import CronTrigger  # type: ignore
from dotenv import load_dotenv
from invest import get_payment

_ = load_dotenv(".env")
TOKEN = str(os.environ.get("bot_token"))

bot = Bot(token=TOKEN)
dp = Dispatcher()

user_ids: set[int] = set()


@dp.message(Command("start"))
async def start_handler(message: Message):
    user_ids.add(message.chat.id)
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Купоны сегодня"), KeyboardButton(text="Мои отчеты")],
            [KeyboardButton(text="Доступные отчеты"), KeyboardButton(text="Помощь")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )

    _ = await message.answer(
        text="Привет! Я Bondelo, делюсь информацией о облигациях", reply_markup=keyboard
    )


@dp.message()
async def handle_buttons(message: Message):
    """Hangle buttons."""
    if message.text == "Купоны сегодня":
        await message.answer(get_payment(), parse_mode="HTML")
    elif message.text == "Помощь":
        await message.answer("Обратитесь к поддержке: https://t.me/your_support_bot")


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
            print(f"Ошибка при отправке {uid}: {e}")


async def main():
    """Start the bot."""
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    _ = scheduler.add_job(send_daily_report, CronTrigger(hour=18, minute=10))
    scheduler.start()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
