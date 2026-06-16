"""Тесты парсинга списка и карточки НРД на сохранённых HTML-фикстурах."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from features.nsd_coupons.parser import (
    _parse_amount,
    _parse_long_date,
    _parse_short_date,
    parse_card,
    parse_listing,
)

_FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def test_parse_listing_extracts_items() -> None:
    items = parse_listing(_load("search_listing.html"))
    assert len(items) == 4

    first = items[0]
    assert first.news_id == 1409937
    assert first.news_type == "INTR"
    assert first.isin == "RU000A105P23"
    assert first.inn == "7717151380"
    assert first.issuer_name == 'Государственная компания "Автодор"'
    assert first.published_at == date(2026, 6, 16)


def test_parse_listing_empty_returns_empty_list() -> None:
    assert parse_listing("<html><body>нет новостей</body></html>") == []


def test_parse_card_extracts_payment_details() -> None:
    card = parse_card(_load("card_intr.html"))
    assert card.news_type == "INTR"
    assert card.planned_pay_date == date(2026, 6, 19)
    assert card.nsd_received_date == date(2026, 6, 15)
    assert card.amount_per_bond == 0.53


def test_parse_short_date() -> None:
    assert _parse_short_date("16.06.2026") == date(2026, 6, 16)
    assert _parse_short_date("нет даты") is None


def test_parse_long_date() -> None:
    assert _parse_long_date("19 июня 2026 г.") == date(2026, 6, 19)
    assert _parse_long_date("1 января 2027") == date(2027, 1, 1)
    assert _parse_long_date("") is None


def test_parse_amount() -> None:
    assert _parse_amount("0.53") == 0.53
    assert _parse_amount("1 647 440,01") == 1647440.01
    assert _parse_amount("") is None
