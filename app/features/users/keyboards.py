"""Keyboards for users/settings feature."""

from aiogram.types import InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .enums import SettingsButtonTexts, SettingsCallbackData


def create_settings_keyboard(has_token: bool) -> InlineKeyboardBuilder:
    """Создаёт инлайн-клавиатуру настроек под текущее состояние токена.

    Единственная кнопка меняет подпись: с токеном она ведёт к замене
    существующего, а не к добавлению ещё одного. Управление конкретными
    брокерами (добавление, замена, удаление) целиком в мини-аппе.

    Args:
        has_token: Подключён ли у пользователя токен хотя бы одного брокера.

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
    return builder


def create_open_miniapp_keyboard(web_app: WebAppInfo) -> InlineKeyboardBuilder:
    """Клавиатура экрана открытия мини-аппа: сама кнопка и возврат в настройки."""
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text=SettingsButtonTexts.OPEN_MINIAPP.value, web_app=web_app)
    )
    builder.add(
        InlineKeyboardButton(
            text=SettingsButtonTexts.BACK.value,
            callback_data=SettingsCallbackData.BACK_TO_SETTINGS.value,
        )
    )
    builder.adjust(1)
    return builder


def settings_text(has_token: bool) -> str:
    """Текст экрана настроек: без статуса токена экран не объясняет свои кнопки."""
    status = "подключён ✅" if has_token else "не подключён ❌"
    return f"<b>Настройки</b>\n\nТокен брокера: {status}"
