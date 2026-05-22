"""Enums for price monitoring feature."""

from enum import Enum


class PriceAlertCallbackData(Enum):
    """Кол-беки для инлайн-кнопок при настройке уведомлений о ценах."""

    PRICE_ALERTS_TOGGLE = "price_alerts_toggle"
    PRICE_ALERTS_SETTINGS = "price_alerts_settings"
    PRICE_ALERTS_DROP_WARNING = "price_alerts_drop_warning"
    PRICE_ALERTS_DROP_CRITICAL = "price_alerts_drop_critical"
    PRICE_ALERTS_RISE_WARNING = "price_alerts_rise_warning"
    PRICE_ALERTS_RISE_CRITICAL = "price_alerts_rise_critical"


class PriceAlertButtonTexts(Enum):
    """Тексты для инлайн-кнопок при настройке уведомлений о ценах."""

    PRICE_ALERTS = "Уведомления о ценах"
    ALERTS_ON = "Вкл. уведомления"
    ALERTS_OFF = "Выкл. уведомления"
    ALERTS_SETTINGS = "Настроить пороги"
    BACK_TO_SETTINGS = "Назад"
