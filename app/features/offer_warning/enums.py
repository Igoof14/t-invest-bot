"""Enums for offer warning feature."""

from enum import Enum


class OfferCallbackData(Enum):
    """Кол-беки для инлайн-кнопок уведомлений об офертах."""

    OFFER_TOGGLE = "offer_toggle"


class OfferAlertButtonTexts(Enum):
    """Тексты для инлайн-кнопок при настройке уведомлений об офертах."""

    ALERTS_ON = "Вкл. уведомления"
    ALERTS_OFF = "Выкл. уведомления"
