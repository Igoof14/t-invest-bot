"""Клавиатуры настроек уведомлений о рейтингах."""

from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .enums import AVAILABLE_AGENCIES, RatingAgency
from .schemas import RatingAlertCallback


def create_rating_alerts_keyboard(enabled: set[RatingAgency]) -> InlineKeyboardBuilder:
    """Создаёт клавиатуру с тумблером на каждое доступное агентство.

    Args:
        enabled: Агентства, на которые пользователь уже подписан.

    Returns:
        Билдер с кнопкой ✅/❌ для каждого агентства из ``AVAILABLE_AGENCIES``.

    """
    builder = InlineKeyboardBuilder()
    for agency in AVAILABLE_AGENCIES:
        mark: str = ": Включено 🔔" if agency in enabled else ": Выключено 🔕"
        builder.add(
            InlineKeyboardButton(
                text=f"{agency.display_name} {mark}",
                callback_data=RatingAlertCallback(action="toggle", agency=agency.value).pack(),
            )
        )
    builder.adjust(1)
    return builder
