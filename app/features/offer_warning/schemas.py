from enum import Enum


class OfferWarningCallbackData(Enum):
    """Кол-беки для инлайн-кнопок при настройке уведомлений об офертах."""

    OFFER_WARNING_TOGGLE = "offer_warning_toggle"


class OfferWarningMessageData(Enum):
    """Данные для сообщений об офертах."""

    pass
