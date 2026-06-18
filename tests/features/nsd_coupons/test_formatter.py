"""Тесты форматирования уведомления о невыплаченном купоне."""

from __future__ import annotations

from datetime import date

from features.nsd_coupons.formatter import format_coupon_miss, format_scan_report
from features.nsd_coupons.schemas import (
    CouponMissAlert,
    CouponScanReport,
    ScannedCoupon,
)


def _alert(**overrides: object) -> CouponMissAlert:
    data: dict[str, object] = {
        "isin": "RU000A105P23",
        "bond_name": "Автодор 005P-01",
        "issuer_name": 'ГК "Автодор"',
        "coupon_number": 7,
        "coupon_date": date(2026, 6, 19),
        "amount": 12.5,
    }
    data.update(overrides)
    return CouponMissAlert(**data)  # type: ignore[arg-type]


def test_format_contains_key_fields() -> None:
    text = format_coupon_miss(_alert())
    assert "Купон не поступил в НРД" in text
    assert "Автодор 005P-01" in text
    assert "<code>RU000A105P23</code>" in text
    assert "№7" in text
    assert "19.06.2026" in text
    assert "12,5" in text


def test_format_without_amount_omits_amount_line() -> None:
    text = format_coupon_miss(_alert(amount=None))
    assert "на 1 бумагу" not in text


def test_format_escapes_html_in_name() -> None:
    text = format_coupon_miss(_alert(bond_name="A & B <test>"))
    assert "A &amp; B &lt;test&gt;" in text


def test_scan_report_no_token() -> None:
    assert "токен" in format_scan_report(CouponScanReport(no_token=True)).lower()


def test_scan_report_empty() -> None:
    assert "не запланировано" in format_scan_report(CouponScanReport()).lower()


def test_scan_report_mixed_paid_and_unpaid() -> None:
    report = CouponScanReport(
        coupons=[
            ScannedCoupon("RU000A105P23", "Автодор", date(2026, 6, 19), paid=True),
            ScannedCoupon("RU000A0JX0J2", "Бонд Б", date(2026, 6, 18), paid=False),
        ]
    )
    text = format_scan_report(report)
    assert "выплачено 1 из 1" in text
    assert "выплачено 0 из 1" in text
    assert "❗ Не поступили" in text
    assert "Бонд Б" in text
    assert "RU000A0JX0J2" in text


def test_scan_report_all_paid() -> None:
    report = CouponScanReport(
        coupons=[ScannedCoupon("RU000A105P23", "Автодор", date(2026, 6, 19), paid=True)]
    )
    assert "✅ Все купоны за период выплачены." in format_scan_report(report)
