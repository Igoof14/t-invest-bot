"""Тесты построения клавиатур уведомлений об офертах."""

from __future__ import annotations

from features.offer_warning.keyboards import (
    create_offer_alert_setting_keyboard,
    create_offer_alerts_keyboard,
)
from features.offer_warning.schemas import OfferAlertCallback


def _actions(builder) -> list[str]:
    """Извлекает action из callback_data всех кнопок клавиатуры."""
    markup = builder.as_markup()
    return [
        OfferAlertCallback.unpack(button.callback_data).action
        for row in markup.inline_keyboard
        for button in row
    ]


def test_alerts_keyboard_enabled_has_toggle_and_setting() -> None:
    actions = _actions(create_offer_alerts_keyboard(True))
    assert actions == ["toggle", "setting"]


def test_alerts_keyboard_disabled_has_only_toggle() -> None:
    builder = create_offer_alerts_keyboard(False)
    assert _actions(builder) == ["toggle"]
    button = builder.as_markup().inline_keyboard[0][0]
    assert button.text == "Оферты: Выключено 🔕"


def test_alerts_keyboard_enabled_toggle_text() -> None:
    button = create_offer_alerts_keyboard(True).as_markup().inline_keyboard[0][0]
    assert button.text == "Оферты: Включено 🔔"


def test_setting_keyboard_has_three_actions() -> None:
    actions = _actions(create_offer_alert_setting_keyboard())
    assert actions == ["set_first", "set_second", "set_time"]
