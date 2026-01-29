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

    # Настройки уведомлений о ценах
    PRICE_ALERTS_TOGGLE = "price_alerts_toggle"
    PRICE_ALERTS_SETTINGS = "price_alerts_settings"
    PRICE_ALERTS_DROP_WARNING = "price_alerts_drop_warning"
    PRICE_ALERTS_DROP_CRITICAL = "price_alerts_drop_critical"
    PRICE_ALERTS_RISE_WARNING = "price_alerts_rise_warning"
    PRICE_ALERTS_RISE_CRITICAL = "price_alerts_rise_critical"


class ButtonTexts(Enum):
    """Enum texts for button."""

    TODAY = "Сегодня"
    WEEK = "Неделю"
    MONTH = "Месяц"
    COUPONS = "Купоны"
    MATURITIES = "Погашения"
    OFFERS = "Оферты"
    MY_REPORTS = "Мои отчеты"
    MONITORING = "Мониторинг"
    HELP = "Помощь"
    SETTINGS = "Настройки"
    ADD_TOKEN = "Добавить токен"
    RM_TOKEN = "Удалить токен"

    # Уведомления о ценах
    PRICE_ALERTS = "Уведомления о ценах"
    ALERTS_ON = "Вкл. уведомления"
    ALERTS_OFF = "Выкл. уведомления"
    ALERTS_SETTINGS = "Настроить пороги"
    BACK_TO_SETTINGS = "Назад"


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
    MATURITIES_TITLE = "<b>Ближайшие погашения облигаций</b>\n\n"
    OFFERS_TITLE = "<b>Ближайшие оферты по облигациям</b>\n\n"
    NO_BONDS = "У вас нет облигаций в портфеле."
    NO_OFFERS = "Нет предстоящих оферт по вашим облигациям на ближайший год."

    # Уведомления о ценах
    PRICE_ALERTS_ENABLED = "Уведомления о ценах облигаций <b>включены</b>.\n\nВы будете получать уведомления при значительных изменениях цен."
    PRICE_ALERTS_DISABLED = "Уведомления о ценах облигаций <b>выключены</b>."
    PRICE_ALERTS_MENU = "<b>Уведомления о ценах облигаций</b>\n\nПолучайте уведомления при аномальных изменениях цен облигаций в вашем портфеле."
    PRICE_ALERTS_SETTINGS_TITLE = "<b>Настройка порогов уведомлений</b>\n\nТекущие пороги:\n"
