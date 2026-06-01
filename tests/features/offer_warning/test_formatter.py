"""Тесты форматирования уведомлений об офертах."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from features.offer_warning import formatter
from features.offer_warning.formatter import _fmt_date, format_offer_alerts

_FROZEN_TODAY = date(2026, 6, 1)


@pytest.fixture(autouse=True)
def _freeze_today(monkeypatch: pytest.MonkeyPatch) -> None:
    """Фиксирует «сегодня» внутри форматтера на 2026-06-01."""

    class _FixedDateTime:
        @classmethod
        def now(cls, tz: ZoneInfo | None = None) -> datetime:
            return datetime(2026, 6, 1, 12, 0, tzinfo=tz)

    monkeypatch.setattr(formatter, "datetime", _FixedDateTime)


def test_fmt_date_formats_date() -> None:
    assert _fmt_date(date(2026, 6, 15)) == "15.06.2026"


def test_fmt_date_returns_dash_for_none() -> None:
    assert _fmt_date(None) == "—"


def test_format_single_offer_contains_name_and_days(offer_factory) -> None:
    # offerdate 2026-06-15 относительно 2026-06-01 → осталось 14 дней
    text = format_offer_alerts([offer_factory(name="ОФЗ-26240")])
    assert "ОФЗ-26240" in text
    assert "осталось <b>14 " in text
    assert "Дата оферты: <b>15.06.2026</b>" in text


def test_format_multiple_offers_renders_each(offer_factory) -> None:
    offers = [
        offer_factory(name="Облигация А", secid="A01"),
        offer_factory(name="Облигация Б", secid="B01"),
    ]
    text = format_offer_alerts(offers)
    assert "Облигация А" in text
    assert "Облигация Б" in text


def test_format_offer_with_offerdateend_shows_deadline_footer(offer_factory) -> None:
    text = format_offer_alerts([offer_factory(offerdateend=date(2026, 6, 10))])
    assert "<b>до 10.06.2026</b>" in text


def test_format_offer_without_offerdateend_shows_generic_footer(offer_factory) -> None:
    text = format_offer_alerts([offer_factory(offerdateend=None)])
    assert "обычно приём заявок закрывается" in text


def test_format_offer_with_price_shows_percent(offer_factory) -> None:
    text = format_offer_alerts([offer_factory(price=98.5)])
    assert "(98.50% от номинала)" in text


def test_format_offer_without_price_omits_percent(offer_factory) -> None:
    text = format_offer_alerts([offer_factory(price=None)])
    assert "% от номинала" not in text


def test_format_offer_uppercases_currency(offer_factory) -> None:
    text = format_offer_alerts([offer_factory(faceunit="rub")])
    assert "RUB" in text


def test_format_offer_shows_agent_when_present(offer_factory) -> None:
    text = format_offer_alerts([offer_factory(agent="ВТБ")])
    assert "Агент: ВТБ" in text


def test_format_offer_omits_agent_when_absent(offer_factory) -> None:
    text = format_offer_alerts([offer_factory(agent=None)])
    assert "Агент:" not in text


def test_format_offer_shows_window_when_dates_present(offer_factory) -> None:
    text = format_offer_alerts(
        [offer_factory(offerdatestart=date(2026, 6, 5), offerdateend=date(2026, 6, 10))]
    )
    assert "Приём заявок: 05.06.2026 – 10.06.2026" in text


def test_format_offer_omits_window_when_dates_absent(offer_factory) -> None:
    text = format_offer_alerts([offer_factory(offerdatestart=None, offerdateend=None)])
    assert "Приём заявок:" not in text
