from enum import Enum


class ReportType(Enum):
    """Enum for report types."""

    DAILY = "daily"
    WEEKLY = "weekly"


class CallbackData(Enum):
    """Enum for callback data in InlineKeyboardButton."""

    COUPONS_TODAY = "coupons_today"
    COUPONS_WEEK = "coupons_week"
    COUPONS_MONTH = "coupons_month"

    ADD_TOKEN = "add_token"
    RM_TOKEN = "rm_token"


class ButtonTexts(Enum):
    """Enum texts for button."""

    TODAY = "Сегодня"
    WEEK = "Неделю"
    MONTH = "Месяц"
    COUPONS = "Купоны"
    MY_REPORTS = "Мои отчеты"
    HELP = "Помощь"
    SETTINGS = "Настройки"
    ADD_TOKEN = "Добавить токен"
    RM_TOKEN = "Удалить токен"


class Messages(Enum):
    """Enum texts for messages."""

    WELCOME = "Привет! Я Bondelo, делюсь информацией о облигациях. \n \n Для начала работы добавьте токен в настройках."
    NOT_TOKEN = "Для начала работы добавьте токен в настройках."
    ALREADY_KNOWN = "Настройки завершены, можно подписаться на отчеты."
    HELP_TEXT = "Обратиться к владельцу: @aleksgoof"
    COUPONS_PROMPT = "Купоны за:"
    COUPONS_TODAY = "Купоны на сегодня \n\n"
    COUPONS_WEEK = "Купоны за неделю \n\n"
    COUPONS_MONTH = "Купоны за месяц \n\n"
