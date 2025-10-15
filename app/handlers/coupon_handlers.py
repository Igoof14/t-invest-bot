"""Обработчики для работы с купонами."""

import logging
from collections.abc import Callable
from datetime import datetime

from aiogram.types import CallbackQuery
from core.enums import CallbackData, Messages
from invest.invest import get_coupon_payment
from utils.datetime_utils import DateTimeHelper

logger = logging.getLogger(__name__)


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
            user_id = callback.from_user.id
            coupon_data = await get_coupon_payment(user_id, start_datetime)
            message_text = title + coupon_data

            if callback.message:
                await callback.message.answer(message_text, parse_mode="HTML")
            await callback.answer()

        except Exception as e:
            logger.error(f"Ошибка при получении купонов: {e}")
            if callback.message:
                await callback.message.answer("Произошла ошибка при получении данных о купонах")
            await callback.answer()
