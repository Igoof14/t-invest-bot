"""Enums for users feature."""

from enum import Enum


class SettingsCallbackData(Enum):
    """Кол-беки для инлайн-кнопок в настройках."""

    ADD_TOKEN = "add_token"
    BACK_TO_SETTINGS = "back_to_settings"


class SettingsButtonTexts(Enum):
    """Тексты для инлайн-кнопок в настройках."""

    ADD_TOKEN = "Подключить токен"
    REPLACE_TOKEN = "Заменить токен"
    OPEN_MINIAPP = "Открыть приложение"
    BACK = "⬅️ Назад"
