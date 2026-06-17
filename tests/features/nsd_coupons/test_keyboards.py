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


def test_keyboard_report_button_shows_time() -> None:
    from datetime import time

    markup = create_coupon_alerts_keyboard(True, report_time=time(21, 0)).as_markup()
    report = markup.inline_keyboard[2][0]
    assert "21:00" in report.text
    assert NsdCouponAlertCallback.unpack(report.callback_data).action == "set_report_time"


def test_keyboard_report_button_off_by_default() -> None:
    markup = create_coupon_alerts_keyboard(True).as_markup()
    assert "выкл" in markup.inline_keyboard[2][0].text
