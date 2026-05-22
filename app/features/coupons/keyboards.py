"""Keyboards for coupons feature."""

from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .enums import CouponButtonTexts, CouponCallbackData


def create_coupons_keyboard() -> InlineKeyboardBuilder:
    """Создает инлайн клавиатуру для выбора периода купонов."""
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(
            text=CouponButtonTexts.TODAY.value,
            callback_data=CouponCallbackData.COUPONS_TODAY.value,
        )
    )
    builder.add(
        InlineKeyboardButton(
            text=CouponButtonTexts.WEEK.value,
            callback_data=CouponCallbackData.COUPONS_WEEK.value,
        )
    )
    builder.add(
        InlineKeyboardButton(
            text=CouponButtonTexts.MONTH.value,
            callback_data=CouponCallbackData.COUPONS_MONTH.value,
        )
    )
    return builder
