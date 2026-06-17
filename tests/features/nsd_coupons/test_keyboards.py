"""Тесты клавиатуры подписки на уведомления о купонах."""

from __future__ import annotations

from features.nsd_coupons.keyboards import create_coupon_alerts_keyboard
from features.nsd_coupons.schemas import NsdCouponAlertCallback


def test_keyboard_shows_enabled_state() -> None:
    markup = create_coupon_alerts_keyboard(enabled=True).as_markup()
    button = markup.inline_keyboard[0][0]
    assert "Включено" in button.text
    assert NsdCouponAlertCallback.unpack(button.callback_data).action == "toggle"


def test_keyboard_shows_disabled_state() -> None:
    markup = create_coupon_alerts_keyboard(enabled=False).as_markup()
    assert "Выключено" in markup.inline_keyboard[0][0].text


def test_keyboard_has_scan_button() -> None:
    markup = create_coupon_alerts_keyboard(enabled=True).as_markup()
    scan = markup.inline_keyboard[1][0]
    assert "Проверить" in scan.text
    assert NsdCouponAlertCallback.unpack(scan.callback_data).action == "scan"
