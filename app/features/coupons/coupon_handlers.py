"""Обработчики для работы с купонами."""

import logging
from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from common.utils.datetime_utils import DateTimeHelper
from core.clients.t_invest.bonds import get_coupon_payment
from .enums import CouponCallbackData

from .keyboards import create_coupons_keyboard

logger = logging.getLogger(__name__)
router = Router()

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


PERIOD_MAPPING = {
    CouponCallbackData.COUPONS_TODAY.value: (
        DateTimeHelper.get_today_start,
        _get_today_title,
    ),
    CouponCallbackData.COUPONS_WEEK.value: (
        DateTimeHelper.get_week_start,
        _get_week_title,
    ),
    CouponCallbackData.COUPONS_MONTH.value: (
        DateTimeHelper.get_month_start,
        _get_month_title,
    ),
}

callback_values = {
    CouponCallbackData.COUPONS_TODAY.value,
    CouponCallbackData.COUPONS_WEEK.value,
    CouponCallbackData.COUPONS_MONTH.value,
}


@router.callback_query(F.data.in_(callback_values))
async def handle_coupon_request(callback: CallbackQuery) -> None:
    """Универсальный обработчик запросов купонов."""
    try:
        if callback.data not in PERIOD_MAPPING:
            await callback.answer("Неизвестный период")
            return

        date_func, title_func = PERIOD_MAPPING[callback.data]
        start_datetime = date_func()
        title = title_func()
        if not callback.from_user:
            await callback.answer("Ошибка идентификации пользователя")
            return
        user_id = callback.from_user.id
        coupon_data = await get_coupon_payment(user_id, start_datetime)
        if not coupon_data:
            await callback.answer("Нет данных о купонах")
            return

        message_text = (
            title
            + "".join(f"{key}: {value:,.0f} ₽\n" for key, value in coupon_data.accounts.items())
            + f"\nИтого: {coupon_data.total_amount:,.0f} ₽"
        )

        if callback.message and isinstance(callback.message, Message):
            keyboard = create_coupons_keyboard()

            await callback.message.edit_text(
                message_text,
                parse_mode="HTML",
                reply_markup=keyboard.as_markup(),
            )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при получении купонов: {e}")
        if callback.message and isinstance(callback.message, Message):
            await callback.message.edit_text("Произошла ошибка при получении данных о купонах")
        await callback.answer()
