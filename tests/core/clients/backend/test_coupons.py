"""Тесты клиента купонных выплат бэкенда."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from core.clients.backend.coupons import get_coupons

ITEM: dict[str, Any] = {
    "bond": {
        "secid": "RU000A10AU73",
        "isin": "RU000A10AU73",
        "shortname": "ГТЛК 2P-07",
        "name": "ГТЛК БО 002P-07",
        "facevalue": "1000",
        "faceunit": "SUR",
        "matdate": "2028-08-04",
    },
    "coupon": {"date": "2026-08-06", "start_date": "2026-05-06", "value_rub": "22.44"},
    "quantity": "80.0000",
    "total_value_rub": "1795.20",
    "is_disclosure": True,
    "disclosure": {
        "total_payment_amount": 224400000.0,
        "payment_per_security_value": 22.44,
        "event_url": "https://e-disclosure.ru/event/123",
    },
    "nsd": {"is_paid": False, "url": None},
    "accounts": [
        {
            "broker": "tbank",
            "account_id": "2045796893",
            "account_name": "ИИСус",
            "quantity": "80.0000",
        }
    ],
}


def _patch_request(monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any]) -> list[tuple]:
    calls: list[tuple] = []

    async def _request(
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        calls.append((method, path, params))
        return payload

    monkeypatch.setattr("core.clients.backend.coupons.request", _request)
    return calls


async def test_parses_item(monkeypatch: pytest.MonkeyPatch) -> None:
    """Полный элемент разбирается со всеми блоками: купон, раскрытие, НРД."""
    _patch_request(monkeypatch, {"date": "2026-08-06", "items": [ITEM]})

    payments = await get_coupons(telegram_id=1825344258)

    assert payments.date == date(2026, 8, 6)
    item = payments.items[0]
    assert item.secid == "RU000A10AU73"
    assert item.shortname == "ГТЛК 2P-07"
    assert item.coupon_date == date(2026, 8, 6)
    assert item.coupon_start_date == date(2026, 5, 6)
    assert item.coupon_value == 22.44
    assert item.total_value == 1795.2
    assert item.quantity == 80.0
    assert item.is_disclosure is True
    assert item.disclosure is not None
    assert item.disclosure.event_url == "https://e-disclosure.ru/event/123"
    assert item.nsd.is_paid is False
    assert item.nsd.url is None
    assert item.moex_link.endswith("code=RU000A10AU73")


async def test_without_date_asks_backend_for_today(monkeypatch: pytest.MonkeyPatch) -> None:
    """Без даты параметр не отправляем: «сегодня» выбирает бэкенд."""
    calls = _patch_request(monkeypatch, {"date": "2026-08-06", "items": []})

    payments = await get_coupons(telegram_id=42)

    assert payments.items == []
    assert calls == [("GET", "/api/v1/users/42/coupons", None)]


async def test_passes_requested_date(monkeypatch: pytest.MonkeyPatch) -> None:
    """Явная дата уходит в query бэкенда в ISO-формате."""
    calls = _patch_request(monkeypatch, {"date": "2026-08-01", "items": []})

    await get_coupons(telegram_id=42, on_date=date(2026, 8, 1))

    assert calls == [("GET", "/api/v1/users/42/coupons", {"date": "2026-08-01"})]


async def test_missing_optional_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Раскрытия может не быть вовсе, а блок НРД бэкенд пока не заполняет."""
    raw = {
        "bond": {"secid": "RU000A106Z38"},
        "coupon": {"date": "2026-08-06"},
        "quantity": "10.0000",
        "is_disclosure": False,
        "disclosure": None,
        "accounts": None,
    }
    _patch_request(monkeypatch, {"date": "2026-08-06", "items": [raw]})

    item = (await get_coupons(telegram_id=42)).items[0]

    assert item.is_disclosure is False
    assert item.disclosure is None
    assert item.nsd.is_paid is False
    assert item.nsd.url is None
    assert item.shortname == "RU000A106Z38"
    assert item.total_value is None
    assert item.accounts == []
