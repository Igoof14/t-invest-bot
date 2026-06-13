"""Клавиатура настроек уведомлений о блокировках ФНС."""

from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .schemas import FnsAlertCallback


def create_fns_alerts_keyboard(enabled: bool) -> InlineKeyboardBuilder:
    """Создаёт клавиатуру с тумблером подписки на уведомления о блокировках.

    Args:
        enabled: Включены ли уведомления у пользователя.

    Returns:
        Билдер с одной кнопкой ✅/🔕.

    """
    builder = InlineKeyboardBuilder()
    mark = "Включено 🔔" if enabled else "Выключено 🔕"
    builder.row(
        InlineKeyboardButton(
            text=f"Блокировки счетов: {mark}",
            callback_data=FnsAlertCallback(action="toggle").pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔍 Проверить моих эмитентов",
            callback_data=FnsAlertCallback(action="scan").pack(),
        )
    )
    return builder
