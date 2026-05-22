"""Base keyboards for the bot."""

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from core.enums import MainKeyboardButtonTexts, NotificationKeybordButtonTexts


def create_main_keyboard() -> ReplyKeyboardMarkup:
    """Создает основную клавиатуру с кнопками."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MainKeyboardButtonTexts.NOTIFICATIONS.value)],
            [
                KeyboardButton(text=MainKeyboardButtonTexts.COUPONS.value),
                KeyboardButton(text=MainKeyboardButtonTexts.MATURITIES.value),
                KeyboardButton(text=MainKeyboardButtonTexts.OFFERS.value),
            ],
            [
                KeyboardButton(text=MainKeyboardButtonTexts.PRICE.value),
                KeyboardButton(text=MainKeyboardButtonTexts.SETTINGS.value),
                KeyboardButton(text=MainKeyboardButtonTexts.HELP.value),
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def create_new_user_keyboard() -> ReplyKeyboardMarkup:
    """Создает клавиатуру для нового пользователя."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MainKeyboardButtonTexts.SETTINGS.value)],
            [KeyboardButton(text=MainKeyboardButtonTexts.HELP.value)],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def create_notifications_keyboard() -> ReplyKeyboardMarkup:
    """Создает клавиатуру раздела уведомлений."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=NotificationKeybordButtonTexts.PRICE_ALERT.value)],
            [KeyboardButton(text=NotificationKeybordButtonTexts.OFFER_ALERT.value)],
            [KeyboardButton(text=NotificationKeybordButtonTexts.BACK_TO_MAIN_KEYBORD.value)],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )
