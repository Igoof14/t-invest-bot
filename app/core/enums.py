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

    ALREADY_KNOWN = "С возвращением! Выберите раздел на клавиатуре ниже."
    HELP_TEXT = "Обратиться к владельцу: @aleksgoof \nЧат участников: @bondelo_chat \nКанал с обновлениями: @bondelo_release"
    COUPONS_PROMPT = "Купоны за:"
    MATURITIES_TITLE = "<b>Ближайшие погашения облигаций</b>\n\n"
    OFFERS_TITLE = "<b>Ближайшие оферты по облигациям</b>\n\n"
    # Пустой экран погашений — не то же самое, что пустой портфель: облигации
    # могут быть, а погашений в ближайшем окне не быть.
    NO_MATURITIES = "Нет предстоящих погашений по вашим облигациям."
    NO_OFFERS = "Нет предстоящих оферт по вашим облигациям на ближайший год."
