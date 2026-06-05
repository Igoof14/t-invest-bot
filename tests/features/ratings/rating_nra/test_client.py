"""Тесты вспомогательных функций клиента НРА."""

from __future__ import annotations

from datetime import datetime

from features.ratings.rating_nra.client import _parse_iso, _stub_from_item


def test_stub_from_item_maps_rest_fields() -> None:
    item = {
        "id": 42241,
        "link": "https://www.ra-national.ru/press_release/test/42241/",
        "title": {"rendered": "НРА подтвердило рейтинг"},
        "modified": "2026-06-03T10:08:31",
    }
    stub = _stub_from_item(item)

    assert stub.uid == "42241"
    assert stub.url == "https://www.ra-national.ru/press_release/test/42241/"
    assert stub.modified == datetime(2026, 6, 3, 10, 8, 31)


def test_parse_iso_invalid() -> None:
    assert _parse_iso(None) is None
    assert _parse_iso("not-a-date") is None
