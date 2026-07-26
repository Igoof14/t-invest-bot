"""Тесты клиента оферт бэкенда."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from core.clients.backend.offers import get_offers

ITEM: dict[str, Any] = {
    "bond": {
        "secid": "RU000A10AS28",
        "isin": "RU000A10AS28",
        "shortname": "БинФарм1P4",
        "name": "Биннофарм Групп 001Р-04",
        "facevalue": "1000",
        "faceunit": "SUR",
        "matdate": "2028-01-22",
    },
    "offer": {
        "date": "2026-08-05",
        "type": "Оферта",
        "date_start": "2026-07-27",
        "date_end": "2026-07-31",
        "price": "100",
        "value": "1000",
        "agent": None,
        "days_left": 10,
    },
    "quantity": "44.0000",
    "accounts": [
        {
            "broker": "tbank",
            "account_id": "2045796893",
            "account_name": "ИИСус",
            "quantity": "30.0000",
        },
        {
            "broker": "tbank",
            "account_id": "2046032553",
            "account_name": "Брокерский счет",
            "quantity": "14.0000",
        },
    ],
}


def _patch_fetch(monkeypatch: pytest.MonkeyPatch, items: list[dict[str, Any]]) -> list[tuple]:
    calls: list[tuple] = []

    async def _fetch(resource: str, telegram_id: int, limit: int) -> list[dict[str, Any]]:
        calls.append((resource, telegram_id, limit))
        return items

    monkeypatch.setattr("core.clients.backend.offers.fetch_user_items", _fetch)
    return calls


async def test_parses_item(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_fetch(monkeypatch, [ITEM])

    offers = await get_offers(telegram_id=1825344258, limit=5)

    assert len(offers) == 1
    item = offers[0]
    assert item.secid == "RU000A10AS28"
    assert item.shortname == "БинФарм1P4"
    assert item.facevalue == 1000.0
    assert item.quantity == 44.0
    assert item.offer_date == date(2026, 8, 5)
    assert item.date_start == date(2026, 7, 27)
    assert item.maturity_date == date(2028, 1, 22)
    assert item.days_left == 10
    assert item.agent is None
    assert item.moex_link.endswith("code=RU000A10AS28")
    assert [acc.account_name for acc in item.accounts] == ["ИИСус", "Брокерский счет"]
    assert item.accounts[1].quantity == 14.0


async def test_requests_offers_resource(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patch_fetch(monkeypatch, [])

    assert await get_offers(telegram_id=42, limit=3) == []
    assert calls == [("offers", 42, 3)]


async def test_nulls_do_not_break_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = {
        "bond": {"secid": "RU000A109874", "facevalue": None, "matdate": None},
        "offer": {"date": "2026-08-07", "date_start": None, "price": None, "days_left": None},
        "quantity": "37.0000",
        "accounts": None,
    }
    _patch_fetch(monkeypatch, [raw])

    item = (await get_offers(telegram_id=42))[0]

    assert item.facevalue is None
    assert item.maturity_date is None
    assert item.date_start is None
    assert item.days_left is None
    assert item.offer_type == "Оферта"
    assert item.shortname == "RU000A109874"
    assert item.accounts == []
