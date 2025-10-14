import logging
from collections.abc import Callable
from datetime import datetime, time, timedelta

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
from core.config import config
from core.enums import ButtonTexts, CallbackData, Messages, ReportType
from invest import get_coupon_payment

logger = logging.getLogger(__name__)

# Хранилище пользователей (лучше заменить на БД)
user_ids: set[int] = set()


class DateTimeHelper:
    """Хелпер для работы с датами."""

    @staticmethod
    def get_today_start() -> datetime:
        """Возвращает начало текущего дня."""
        return datetime.combine(datetime.today().date(), time.min)

    @staticmethod
    def get_week_start() -> datetime:
        """Возвращает начало текущей недели (понедельник)."""
        today = datetime.today()
        return datetime.combine(
            today.date() - timedelta(days=today.weekday()),
            time.min,
        )

    @staticmethod
    def get_month_start() -> datetime:
        """Возвращает начало текущего месяца."""
        today = datetime.today()
        return datetime.combine(
            today.date() - timedelta(days=today.day - 1),
            time.min,
        )


class KeyboardHelper:
    """Хелпер для создания клавиатур."""

    @staticmethod
    def create_coupons_inline_keyboard() -> InlineKeyboardBuilder:
        """Создает инлайн клавиатуру для выбора периода купонов."""
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(
                text=ButtonTexts.TODAY.value,
                callback_data=CallbackData.COUPONS_TODAY.value,
            )
        )
        builder.add(
            InlineKeyboardButton(
                text=ButtonTexts.WEEK.value,
                callback_data=CallbackData.COUPONS_WEEK.value,
            )
        )
        builder.add(
            InlineKeyboardButton(
                text=ButtonTexts.MONTH.value,
                callback_data=CallbackData.COUPONS_MONTH.value,
            )
        )
        return builder

    @staticmethod
    def create_main_keyboard() -> ReplyKeyboardMarkup:
        """Создает основную клавиатуру с кнопками."""
        return ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text=ButtonTexts.COUPONS.value),
                    KeyboardButton(text=ButtonTexts.MY_REPORTS.value),
                ],
                [KeyboardButton(text=ButtonTexts.HELP.value)],
            ],
            resize_keyboard=True,
            one_time_keyboard=False,
        )


class CouponHandler:
    """Обработчик купонов."""

    PERIOD_MAPPING: dict[str, tuple[Callable[[], datetime], str]] = {
        CallbackData.COUPONS_TODAY.value: (
            DateTimeHelper.get_today_start,
            Messages.COUPONS_TODAY.value,
        ),
        CallbackData.COUPONS_WEEK.value: (
            DateTimeHelper.get_week_start,
            Messages.COUPONS_WEEK.value,
        ),
        CallbackData.COUPONS_MONTH.value: (
            DateTimeHelper.get_month_start,
            Messages.COUPONS_MONTH.value,
        ),
    }

    @classmethod
    async def handle_coupon_request(cls, callback: CallbackQuery) -> None:
        """Универсальный обработчик запросов купонов."""
        try:
            if callback.data not in cls.PERIOD_MAPPING:
                await callback.answer("Неизвестный период")
                return

            date_func, title = cls.PERIOD_MAPPING[callback.data]
            start_datetime = date_func()

            coupon_data = get_coupon_payment(start_datetime)
            message_text = title + coupon_data

            if callback.message:
                await callback.message.answer(message_text, parse_mode="HTML")
            await callback.answer()

        except Exception as e:
            logger.error(f"Ошибка при получении купонов: {e}")
            if callback.message:
                await callback.message.answer("Произошла ошибка при получении данных о купонах")
            await callback.answer()


def register_handlers(dp: Dispatcher, bot: Bot) -> None:
    """Регистрируем все хендлеры тут."""
    callback_values = {
        CallbackData.COUPONS_TODAY.value,
        CallbackData.COUPONS_WEEK.value,
        CallbackData.COUPONS_MONTH.value,
    }

    @dp.callback_query(F.data.in_(callback_values))
    async def handle_coupon_callbacks(callback: CallbackQuery) -> None:
        await CouponHandler.handle_coupon_request(callback)

    @dp.message(Command("start"))
    async def start_handler(message: Message) -> None:
        """Start handler."""
        try:
            keyboard = KeyboardHelper.create_main_keyboard()

            if message.chat.id not in user_ids:
                user_ids.add(message.chat.id)
                await message.answer(Messages.WELCOME.value, reply_markup=keyboard)
            else:
                await message.answer(Messages.ALREADY_KNOWN.value, reply_markup=keyboard)

        except Exception as e:
            logger.error(f"Ошибка в start handler: {e}")
            await message.answer("Произошла ошибка при запуске")

    @dp.message(F.text == ButtonTexts.COUPONS.value)
    async def handle_coupons_button(message: Message) -> None:
        """Обработка кнопки 'Купоны'."""
        try:
            builder = KeyboardHelper.create_coupons_inline_keyboard()
            await message.answer(Messages.COUPONS_PROMPT.value, reply_markup=builder.as_markup())
        except Exception as e:
            logger.error(f"Ошибка при обработке кнопки купонов: {e}")
            await message.answer("Произошла ошибка")

    @dp.message(F.text == ButtonTexts.HELP.value)
    async def handle_help_button(message: Message) -> None:
        """Обработка кнопки 'Помощь'."""
        try:
            await message.answer(Messages.HELP_TEXT.value)
        except Exception as e:
            logger.error(f"Ошибка при обработке кнопки помощи: {e}")


async def set_commands(bot: Bot) -> None:
    """Установка команд."""
    commands = [
        BotCommand(command="start", description="Запустить бота"),
    ]
    await bot.set_my_commands(commands)


async def send_report(bot: Bot, report_type: ReportType) -> None:
    """Рассылка отчёта."""
    if not user_ids:
        logger.info("Нет пользователей для рассылки")
        return

    try:
        if report_type.value == "daily":
            start_datetime = DateTimeHelper.get_today_start()
        elif report_type.value == "weekly":
            start_datetime = DateTimeHelper.get_week_start()
        else:
            logger.error(f"Неизвестный тип отчета: {report_type.value}")
            return

        text = get_coupon_payment(start_datetime=start_datetime)

        failed_users = []
        for uid in user_ids.copy():
            try:
                await bot.send_message(uid, text, parse_mode="HTML")
            except Exception as e:
                logger.error(f"Ошибка при отправке пользователю {uid}: {e}")
                failed_users.append(uid)

        for uid in failed_users:
            user_ids.discard(uid)

        logger.info(f"Отчет отправлен {len(user_ids)} пользователям")

    except Exception as e:
        logger.error(f"Ошибка при рассылке отчета: {e}")
