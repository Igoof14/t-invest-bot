import asyncio
import logging
import os
from datetime import datetime, time, timedelta
from random import randint

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore
from apscheduler.triggers.cron import CronTrigger  # type: ignore
from config import config
from dotenv import load_dotenv
from enums import ReportType
from invest import get_coupon_payment_today

logging.basicConfig(level=logging.INFO)

bot = Bot(token=config.bot_token.get_secret_value())
dp = Dispatcher()

user_ids: set[int] = set()


@dp.message(Command("inline_url"))
async def cmd_inline_url(message: Message, bot: Bot):
    """Inline URL handler."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="GitHub", url="https://github.com"))
    builder.row(InlineKeyboardButton(text="Оф. канал Telegram", url="tg://resolve?domain=telegram"))

    await message.answer(
        "Выберите ссылку",
        reply_markup=builder.as_markup(),
    )


@dp.callback_query(F.data == "random_value")
async def send_random_value(callback: CallbackQuery):
    """Send random value."""
    await callback.message.answer(str(randint(1, 10)))  # type: ignore
    await callback.answer(text="Спасибо, что воспользовались ботом!", show_alert=True)


@dp.message(Command("random"))
async def cmd_random(message: Message):
    """Get Callback handler."""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Нажми меня", callback_data="random_value"))
    builder.add(InlineKeyboardButton(text="Нажми меня 2", callback_data="random_value"))
    await message.answer(
        "Нажмите на кнопку, чтобы бот отправил число от 1 до 10", reply_markup=builder.as_markup()
    )


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
            [
                KeyboardButton(text="Донат"),
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )
    if message.chat.id not in user_ids:
        user_ids.add(message.chat.id)

        _ = await message.answer(
            text=f"Привет! Я Bondelo, делюсь информацией о облигациях",
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

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
