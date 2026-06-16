"""Тесты клавиатуры подписки на уведомления о купонах."""

from __future__ import annotations

from features.nsd_coupons.keyboards import create_coupon_alerts_keyboard
from features.nsd_coupons.schemas import NsdCouponAlertCallback


def test_keyboard_shows_enabled_state() -> None:
    markup = create_coupon_alerts_keyboard(enabled=True)
    button = markup.inline_keyboard[0][0]
    assert "Включено" in button.text
    assert NsdCouponAlertCallback.unpack(button.callback_data).action == "toggle"


def test_keyboard_shows_disabled_state() -> None:
    markup = create_coupon_alerts_keyboard(enabled=False)
    assert "Выключено" in markup.inline_keyboard[0][0].text
