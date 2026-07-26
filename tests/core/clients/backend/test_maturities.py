"""Тесты клиента погашений бэкенда."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from core.clients.backend.maturities import get_maturities

ITEM: dict[str, Any] = {
    "bond": {
        "secid": "RU000A10AU73",
        "isin": "RU000A10AU73",
        "shortname": "ГТЛК 2P-07",
        "name": "ГТЛК БО 002P-07",
        "facevalue": "1000",
        "faceunit": "SUR",
        "matdate": "2026-08-04",
    },
    "maturity": {"date": "2026-08-04", "days_left": 9},
    "quantity": "80.0000",
    "accounts": [
        {
            "broker": "tbank",
            "account_id": "2045796893",
            "account_name": "ИИСус",
            "quantity": "40.0000",
        },
        {
            "broker": "tbank",
            "account_id": "2046032553",
            "account_name": "Брокерский счет",
            "quantity": "40.0000",
        },
    ],
}


def _patch_fetch(monkeypatch: pytest.MonkeyPatch, items: list[dict[str, Any]]) -> list[tuple]:
    calls: list[tuple] = []

    async def _fetch(resource: str, telegram_id: int, limit: int) -> list[dict[str, Any]]:
        calls.append((resource, telegram_id, limit))
        return items

    monkeypatch.setattr("core.clients.backend.maturities.fetch_user_items", _fetch)
    return calls


async def test_parses_item(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_fetch(monkeypatch, [ITEM])

    maturities = await get_maturities(telegram_id=1825344258, limit=5)

    assert len(maturities) == 1
    item = maturities[0]
    assert item.secid == "RU000A10AU73"
    assert item.shortname == "ГТЛК 2P-07"
    assert item.facevalue == 1000.0
    assert item.quantity == 80.0
    assert item.maturity_date == date(2026, 8, 4)
    assert item.days_left == 9
    assert item.moex_link.endswith("code=RU000A10AU73")
    assert [acc.quantity for acc in item.accounts] == [40.0, 40.0]


async def test_requests_maturities_resource(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patch_fetch(monkeypatch, [])

    assert await get_maturities(telegram_id=42, limit=3) == []
    assert calls == [("maturities", 42, 3)]


async def test_falls_back_to_bond_matdate(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = {
        "bond": {"secid": "RU000A106Z38", "facevalue": "150", "matdate": "2026-09-29"},
        "maturity": {"date": None, "days_left": None},
        "quantity": "10.0000",
        "accounts": None,
    }
    _patch_fetch(monkeypatch, [raw])

    item = (await get_maturities(telegram_id=42))[0]

    assert item.maturity_date == date(2026, 9, 29)
    assert item.days_left is None
    assert item.shortname == "RU000A106Z38"
    assert item.accounts == []
