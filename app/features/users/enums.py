"""Enums for users feature."""

from enum import Enum


class SettingsCallbackData(Enum):
    """Кол-беки для инлайн-кнопок в настройках."""

    ADD_TOKEN = "add_token"
    RM_TOKEN = "rm_token"


class SettingsButtonTexts(Enum):
    """Тексты для инлайн-кнопок в настройках."""

    ADD_TOKEN = "Добавить токен"
    RM_TOKEN = "Удалить токен"
