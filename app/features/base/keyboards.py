"""Base keyboards for the bot."""

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from core.enums import MainKeyboardButtonTexts


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
    """Создает клавиатуру для пользователя без токена.

    Раскладка та же, что и у основной: без токена бот присылает уведомления по
    всему рынку, а значит «Уведомления» должны открываться — иначе настройки
    оказываются недоступны. Портфельные разделы остаются на месте и отвечают
    заглушкой (см. :data:`common.token_gate.TOKEN_REQUIRED`): прятать кнопки
    смысла нет — так видно, что появится после подключения токена.
    """
    return create_main_keyboard()
