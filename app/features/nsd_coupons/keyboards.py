"""Клавиатура настроек уведомлений о невыплаченных купонах."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .schemas import NsdCouponAlertCallback


def create_coupon_alerts_keyboard(enabled: bool) -> InlineKeyboardMarkup:
    """Создаёт клавиатуру с тумблером подписки на уведомления о купонах.

    Args:
        enabled: Включены ли уведомления у пользователя.

    Returns:
        Разметка с одной кнопкой-тумблером.
    """
    builder = InlineKeyboardBuilder()
    mark = "Включено 🔔" if enabled else "Выключено 🔕"
    builder.row(
        InlineKeyboardButton(
            text=f"Купоны не пришли: {mark}",
            callback_data=NsdCouponAlertCallback(action="toggle").pack(),
        )
    )
    return builder.as_markup()
