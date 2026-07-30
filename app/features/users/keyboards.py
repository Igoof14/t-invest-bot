"""Keyboards for users/settings feature."""

from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .enums import SettingsButtonTexts, SettingsCallbackData


def create_settings_keyboard(has_token: bool) -> InlineKeyboardBuilder:
    """Создаёт инлайн-клавиатуру настроек под текущее состояние токена.

    Удалять нечего, пока токен не подключён, — кнопки удаления в этом случае
    просто нет. А кнопка подключения меняет подпись: с токеном она перезаписывает
    существующий, а не «добавляет» ещё один.

    Args:
        has_token: Подключён ли у пользователя токен T-Invest.

    """
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(
            text=(
                SettingsButtonTexts.REPLACE_TOKEN.value
                if has_token
                else SettingsButtonTexts.ADD_TOKEN.value
            ),
            callback_data=SettingsCallbackData.ADD_TOKEN.value,
        )
    )
    if has_token:
        builder.add(
            InlineKeyboardButton(
                text=SettingsButtonTexts.RM_TOKEN.value,
                callback_data=SettingsCallbackData.RM_TOKEN.value,
            )
        )
    builder.adjust(2)
    return builder


def create_delete_confirm_keyboard() -> InlineKeyboardBuilder:
    """Клавиатура подтверждения удаления токена: «Да, удалить» / «Отмена»."""
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(
            text=SettingsButtonTexts.RM_TOKEN_CONFIRM.value,
            callback_data=SettingsCallbackData.RM_TOKEN_CONFIRM.value,
        )
    )
    builder.add(
        InlineKeyboardButton(
            text=SettingsButtonTexts.CANCEL.value,
            callback_data=SettingsCallbackData.RM_TOKEN_CANCEL.value,
        )
    )
    builder.adjust(2)
    return builder


def create_token_input_keyboard() -> InlineKeyboardBuilder:
    """Клавиатура экрана ввода токена: единственный выход из ожидания ввода."""
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(
            text=SettingsButtonTexts.CANCEL.value,
            callback_data=SettingsCallbackData.TOKEN_INPUT_CANCEL.value,
        )
    )
    return builder


def settings_text(has_token: bool) -> str:
    """Текст экрана настроек: без статуса токена экран не объясняет свои кнопки."""
    status = "подключён ✅" if has_token else "не подключён ❌"
    return f"<b>Настройки</b>\n\nТокен T-Invest: {status}"
