"""Обработчики для работы с купонами."""

import logging
from datetime import datetime, timedelta

from aiogram.types import CallbackQuery
from core.enums import CallbackData
from invest.invest import get_coupon_payment
from keyboards import KeyboardHelper
from utils.datetime_utils import DateTimeHelper

logger = logging.getLogger(__name__)

MONTH_NAMES = [
    "",
    "январь",
    "февраль",
    "март",
    "апрель",
    "май",
    "июнь",
    "июль",
    "август",
    "сентябрь",
    "октябрь",
    "ноябрь",
    "декабрь",
]

MONTH_NAMES_SHORT = [
    "",
    "янв",
    "фев",
    "мар",
    "апр",
    "мая",
    "июн",
    "июл",
    "авг",
    "сен",
    "окт",
    "ноя",
    "дек",
]


def _get_today_title() -> str:
    """Заголовок для купонов за сегодня."""
    today = datetime.today()
    return f"<b>Купоны на {today.day} {MONTH_NAMES_SHORT[today.month]}</b>\n\n"


def _get_week_title() -> str:
    """Заголовок для купонов за текущую неделю."""
    today = datetime.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    return f"<b>Купоны с {week_start.day} {MONTH_NAMES_SHORT[week_start.month]} по {week_end.day} {MONTH_NAMES_SHORT[week_end.month]}</b>\n\n"


def _get_month_title() -> str:
    """Заголовок для купонов за текущий месяц."""
    today = datetime.today()
    return f"<b>Купоны за {MONTH_NAMES[today.month]}</b>\n\n"


class CouponHandler:
    """Обработчик купонов."""

    PERIOD_MAPPING = {
        CallbackData.COUPONS_TODAY.value: (
            DateTimeHelper.get_today_start,
            _get_today_title,
        ),
        CallbackData.COUPONS_WEEK.value: (
            DateTimeHelper.get_week_start,
            _get_week_title,
        ),
        CallbackData.COUPONS_MONTH.value: (
            DateTimeHelper.get_month_start,
            _get_month_title,
        ),
    }

    @classmethod
    async def handle_coupon_request(cls, callback: CallbackQuery) -> None:
        """Универсальный обработчик запросов купонов."""
        try:
            if callback.data not in cls.PERIOD_MAPPING:
                await callback.answer("Неизвестный период")
                return

            date_func, title_func = cls.PERIOD_MAPPING[callback.data]
            start_datetime = date_func()
            title = title_func()
            user_id = callback.from_user.id
            coupon_data = await get_coupon_payment(user_id, start_datetime)
            message_text = title + coupon_data

            if callback.message:
                keyboard = KeyboardHelper.create_coupons_inline_keyboard()
                await callback.message.edit_text(
                    message_text,
                    parse_mode="HTML",
                    reply_markup=keyboard.as_markup(),
                )
            await callback.answer()

        except Exception as e:
            logger.error(f"Ошибка при получении купонов: {e}")
            if callback.message:
                await callback.message.edit_text(
                    "Произошла ошибка при получении данных о купонах"
                )
            await callback.answer()
