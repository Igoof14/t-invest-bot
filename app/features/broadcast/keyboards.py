"""Клавиатуры админской рассылки."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .schemas import BROADCAST_CANCEL, BROADCAST_CONFIRM


def confirm_keyboard() -> InlineKeyboardBuilder:
    """Инлайн-клавиатура подтверждения рассылки."""
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="📣 Отправить", callback_data=BROADCAST_CONFIRM),
        InlineKeyboardButton(text="Отмена", callback_data=BROADCAST_CANCEL),
    )
    builder.adjust(2)
    return builder
