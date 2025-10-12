import asyncio
import os
from datetime import datetime, time, timedelta
from enum import Enum

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import BotCommand, KeyboardButton, Message, ReplyKeyboardMarkup
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore
from apscheduler.triggers.cron import CronTrigger  # type: ignore
from dotenv import load_dotenv
from enums import ReportType
from invest import get_coupon_payment_today

_ = load_dotenv(".env")
TOKEN = str(os.environ.get("bot_token"))


bot = Bot(token=TOKEN)
dp = Dispatcher()

user_ids: set[int] = set()


@dp.message(Command("start"))
async def start_handler(message: Message):
    """Start handler."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="Купоны сегодня"),
                KeyboardButton(text="Купоны за неделю"),
            ],
            [
                KeyboardButton(text="Мои отчеты"),
                KeyboardButton(text="Доступные отчеты"),
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )
    if message.chat.id not in user_ids:
        user_ids.add(message.chat.id)

        _ = await message.answer(
            text=f"Привет! Я Bondelo, делюсь информацией о облигациях, user_id: {message.chat.id}",
            reply_markup=keyboard,
        )
    else:
        _ = await message.answer(text="А я тебя знаю!", reply_markup=keyboard)


@dp.message()
async def handle_buttons(message: Message):
    """Hangle buttons."""
    if message.text == "Купоны сегодня":
        today_midnight = datetime.combine(datetime.today().date(), time.min)
        await message.answer(
            get_coupon_payment_today(start_datetime=today_midnight), parse_mode="HTML"
        )
    elif message.text == "Купоны за неделю":
        today = datetime.today()
        start_datetime = datetime.combine(
            today.date() - timedelta(days=today.weekday()),
            time.min,
        )
        await message.answer(
            get_coupon_payment_today(start_datetime=start_datetime), parse_mode="HTML"
        )
    elif message.text == "Помощь":
        await message.answer("Обратитесь к поддержке: https://t.me/your_support_bot")


async def set_commands(bot: Bot):
    """Set commands."""
    commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="report", description="Получить отчёт по облигациям"),
    ]
    await bot.set_my_commands(commands)


async def send_report(report_type: ReportType):
    """Рассылка отчёта."""
    if not user_ids:
        return

    if not report_type:
        return

    if report_type.value == "daily":
        start_datetime = datetime.combine(datetime.today().date(), time.min)
    elif report_type.value == "weekly":
        today = datetime.today()
        start_datetime = datetime.combine(
            today.date() - timedelta(days=today.weekday()),
            time.min,
        )

    text = get_coupon_payment_today(start_datetime=start_datetime)
    for uid in user_ids:
        try:
            await bot.send_message(uid, text, parse_mode="HTML")
        except Exception as e:
            print(f"Ошибка при отправке {uid}: {e}")


async def main():
    """Start the bot."""
    await set_commands(bot)
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

    scheduler.add_job(
        send_report, CronTrigger(hour=18, minute=10), kwargs={"report_type": ReportType.DAILY}
    )

    scheduler.add_job(
        send_report,
        CronTrigger(day_of_week="fri", hour=18, minute=10, second=1),
        kwargs={"report_type": ReportType.WEEKLY},
    )
    scheduler.start()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
