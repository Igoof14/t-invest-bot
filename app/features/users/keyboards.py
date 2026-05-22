"""Keyboards for users/settings feature."""

from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .enums import SettingsButtonTexts, SettingsCallbackData


def create_settings_keyboard() -> InlineKeyboardBuilder:
    """Создает инлайн клавиатуру для настроек."""
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(
            text=SettingsButtonTexts.ADD_TOKEN.value,
            callback_data=SettingsCallbackData.ADD_TOKEN.value,
        )
    )
    builder.add(
        InlineKeyboardButton(
            text=SettingsButtonTexts.RM_TOKEN.value,
            callback_data=SettingsCallbackData.RM_TOKEN.value,
        )
    )
    builder.adjust(2)
    return builder
