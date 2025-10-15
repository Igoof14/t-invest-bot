"""Основные клавиатуры для бота."""

from aiogram.types import InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from core.enums import ButtonTexts, CallbackData


class KeyboardHelper:
    """Хелпер для создания клавиатур."""

    @staticmethod
    def create_coupons_inline_keyboard() -> InlineKeyboardBuilder:
        """Создает инлайн клавиатуру для выбора периода купонов."""
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(
                text=ButtonTexts.TODAY.value,
                callback_data=CallbackData.COUPONS_TODAY.value,
            )
        )
        builder.add(
            InlineKeyboardButton(
                text=ButtonTexts.WEEK.value,
                callback_data=CallbackData.COUPONS_WEEK.value,
            )
        )
        builder.add(
            InlineKeyboardButton(
                text=ButtonTexts.MONTH.value,
                callback_data=CallbackData.COUPONS_MONTH.value,
            )
        )
        return builder

    @staticmethod
    def create_settings_keyboard() -> InlineKeyboardBuilder:
        """Создает инлайн клавиатуру для настроек."""
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(
                text=ButtonTexts.ADD_TOKEN.value,
                callback_data=CallbackData.ADD_TOKEN.value,
            )
        )
        builder.add(
            InlineKeyboardButton(
                text=ButtonTexts.RM_TOKEN.value,
                callback_data=CallbackData.RM_TOKEN.value,
            )
        )

        return builder

    @staticmethod
    def create_main_keyboard() -> ReplyKeyboardMarkup:
        """Создает основную клавиатуру с кнопками."""
        return ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text=ButtonTexts.COUPONS.value),
                    KeyboardButton(text=ButtonTexts.MY_REPORTS.value),
                ],
                [KeyboardButton(text=ButtonTexts.SETTINGS.value)],
                [KeyboardButton(text=ButtonTexts.HELP.value)],
            ],
            resize_keyboard=True,
            one_time_keyboard=False,
        )

    @staticmethod
    def create_new_user_keyboard() -> ReplyKeyboardMarkup:
        """Создает клавиатуру для нового пользователя."""
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=ButtonTexts.SETTINGS.value)],
                [KeyboardButton(text=ButtonTexts.HELP.value)],
            ],
            resize_keyboard=True,
            one_time_keyboard=False,
        )
