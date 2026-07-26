from enum import Enum


class MainKeyboardButtonTexts(Enum):
    """Тексты кнопок для основной клавиатуры."""

    COUPONS = "Купоны"
    MATURITIES = "Погашения"
    OFFERS = "Оферты"
    PRICE = "Цена"
    NOTIFICATIONS = "Уведомления"
    HELP = "Помощь"
    SETTINGS = "Настройки"


class Messages(Enum):
    """Enum texts for messages."""

    WELCOME = "Привет! Я Bondelo, делюсь информацией о облигациях. \n \n Для начала работы добавьте токен в настройках."
    NOT_TOKEN = "Для начала работы добавьте токен в настройках."
    ALREADY_KNOWN = "Настройки завершены, можно подписаться на отчеты."
    HELP_TEXT = "Обратиться к владельцу: @aleksgoof \nЧат участников: @bondelo_chat"
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
