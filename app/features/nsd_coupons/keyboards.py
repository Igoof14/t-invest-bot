"""Клавиатура настроек уведомлений о невыплаченных купонах."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .schemas import NsdCouponAlertCallback


def create_coupon_alerts_keyboard(enabled: bool) -> InlineKeyboardBuilder:
    """Создаёт билдер с тумблером подписки на уведомления о купонах.

    Возвращает билдер (а не готовую разметку), чтобы секция меню могла добавить
    к нему кнопки «как это работает» и «назад».

    Args:
        enabled: Включены ли уведомления у пользователя.

    Returns:
        Билдер с одной кнопкой-тумблером.
    """
    builder = InlineKeyboardBuilder()
    mark = "Включено 🔔" if enabled else "Выключено 🔕"
    builder.row(
        InlineKeyboardButton(
            text=f"Купоны не пришли: {mark}",
            callback_data=NsdCouponAlertCallback(action="toggle").pack(),
        )
    )
    return builder
