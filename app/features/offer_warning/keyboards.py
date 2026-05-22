"""Keyboards for offer warning feature."""

from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .enums import OfferAlertButtonTexts, OfferCallbackData


def create_offer_alerts_keyboard(alerts_enabled: bool) -> InlineKeyboardBuilder:
    """Создает инлайн клавиатуру для настроек уведомлений об офертах.

    Args:
        alerts_enabled: Включены ли уведомления

    """
    builder = InlineKeyboardBuilder()

    toggle_text = (
        OfferAlertButtonTexts.ALERTS_OFF.value
        if alerts_enabled
        else OfferAlertButtonTexts.ALERTS_ON.value
    )
    builder.add(
        InlineKeyboardButton(
            text=toggle_text,
            callback_data=OfferCallbackData.OFFER_TOGGLE.value,
        )
    )
    return builder
