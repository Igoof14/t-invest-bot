"""Keyboards for price monitoring feature."""

from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .enums import PriceAlertButtonTexts, PriceAlertCallbackData


def create_price_alerts_keyboard(alerts_enabled: bool) -> InlineKeyboardBuilder:
    """Создает инлайн клавиатуру для настроек уведомлений о ценах.

    Args:
        alerts_enabled: Включены ли уведомления

    """
    builder = InlineKeyboardBuilder()

    toggle_text = (
        PriceAlertButtonTexts.ALERTS_ENABLED.value
        if alerts_enabled
        else PriceAlertButtonTexts.ALERTS_DISABLED.value
    )
    builder.add(
        InlineKeyboardButton(
            text=toggle_text,
            callback_data=PriceAlertCallbackData.PRICE_ALERTS_TOGGLE.value,
        )
    )

    if alerts_enabled:
        builder.add(
            InlineKeyboardButton(
                text=PriceAlertButtonTexts.ALERTS_SETTINGS.value,
                callback_data=PriceAlertCallbackData.PRICE_ALERTS_SETTINGS.value + "_thresholds",
            )
        )

    builder.adjust(1)
    return builder


def create_thresholds_keyboard() -> InlineKeyboardBuilder:
    """Создает клавиатуру для настройки порогов уведомлений."""
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(
            text="Падение умеренное",
            callback_data=PriceAlertCallbackData.PRICE_ALERTS_DROP_WARNING.value,
        )
    )
    builder.add(
        InlineKeyboardButton(
            text="Рост умеренный",
            callback_data=PriceAlertCallbackData.PRICE_ALERTS_RISE_WARNING.value,
        )
    )
    builder.add(
        InlineKeyboardButton(
            text="Падение сильное",
            callback_data=PriceAlertCallbackData.PRICE_ALERTS_DROP_CRITICAL.value,
        )
    )
    builder.add(
        InlineKeyboardButton(
            text="Рост сильный",
            callback_data=PriceAlertCallbackData.PRICE_ALERTS_RISE_CRITICAL.value,
        )
    )
    builder.add(
        InlineKeyboardButton(
            text=PriceAlertButtonTexts.BACK_TO_SETTINGS.value,
            callback_data=PriceAlertCallbackData.PRICE_ALERTS_SETTINGS.value,
        )
    )

    builder.adjust(2, 2, 1)
    return builder
