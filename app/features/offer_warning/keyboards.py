"""Keyboards for offer warning feature."""

from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .schemas import OfferAlertCallback


def create_offer_alerts_keyboard(alerts_enabled: bool) -> InlineKeyboardBuilder:
    """Создает инлайн клавиатуру для настроек уведомлений об офертах.

    Args:
        alerts_enabled: Включены ли уведомления

    """
    builder = InlineKeyboardBuilder()
    toggle_text = "Выкл. уведомления" if alerts_enabled else "Вкл. уведомления"
    builder.add(
        InlineKeyboardButton(
            text=toggle_text,
            callback_data=OfferAlertCallback(action="toggle").pack(),
        )
    )
    if alerts_enabled:
        builder.add(
            InlineKeyboardButton(
                text="Настроить",
                callback_data=OfferAlertCallback(action="setting").pack(),
            )
        )
    builder.adjust(1)
    return builder


def create_offer_alert_setting_keyboard() -> InlineKeyboardBuilder:
    """Создает инлайн клавиатуру для настроек уведомлений об офертах."""
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(
            text="Первое",
            callback_data=OfferAlertCallback(action="set_first").pack(),
        )
    )
    builder.add(
        InlineKeyboardButton(
            text="Второе",
            callback_data=OfferAlertCallback(action="set_second").pack(),
        )
    )
    builder.add(
        InlineKeyboardButton(
            text="Время уведомления",
            callback_data=OfferAlertCallback(action="set_time").pack(),
        )
    )

    builder.adjust(2, 1)
    return builder
