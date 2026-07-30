"""Enums for users feature."""

from enum import Enum


class SettingsCallbackData(Enum):
    """Кол-беки для инлайн-кнопок в настройках."""

    ADD_TOKEN = "add_token"
    RM_TOKEN = "rm_token"
    RM_TOKEN_CONFIRM = "rm_token_confirm"
    RM_TOKEN_CANCEL = "rm_token_cancel"
    TOKEN_INPUT_CANCEL = "token_input_cancel"


class SettingsButtonTexts(Enum):
    """Тексты для инлайн-кнопок в настройках."""

    ADD_TOKEN = "Подключить токен"
    REPLACE_TOKEN = "Заменить токен"
    RM_TOKEN = "Удалить токен"
    RM_TOKEN_CONFIRM = "Да, удалить"
    CANCEL = "Отмена"
    BACK = "⬅️ Назад"
