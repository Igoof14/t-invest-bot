"""Тесты разовой проверки купонов (scan_user)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from features.nsd_coupons import service as service_module
from features.nsd_coupons.schemas import CouponPlan
from features.nsd_coupons.service import NsdCouponService

_FIXTURES = Path(__file__).parent / "fixtures"
_LISTING = (_FIXTURES / "search_listing.html").read_text(encoding="utf-8")
_CARD = (_FIXTURES / "card_intr.html").read_text(encoding="utf-8")


class _FakeClient:
    """Заглушка NsdClient: отдаёт сохранённые HTML (карточка — плановая 19.06)."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    async def search_by_isin(self, isin: str, **kwargs: object) -> str:
        return _LISTING

    async def fetch_card(self, news_id: int) -> str:
        return _CARD


def _plan(coupon_number: int, coupon_date: date) -> CouponPlan:
    return CouponPlan(
        isin="RU000A105P23",
        figi="FG",
        coupon_number=coupon_number,
        coupon_date=coupon_date,
        bond_name="Автодор",
    )


async def test_scan_user_reports_paid_and_unpaid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(service_module, "NsdClient", _FakeClient)
    monkeypatch.setattr(
        service_module.BotUserRepository,
        "get_token_by_telegram_id",
        AsyncMock(return_value="token"),
    )

    # Купон на сегодня (19.06) совпадёт с карточкой → paid; на вчера (18.06) — нет.
    async def fake_collect(telegram_id: int, *a: object, **k: object) -> list[CouponPlan]:
        return [_plan(99, date(2026, 6, 19)), _plan(98, date(2026, 6, 18))]

    monkeypatch.setattr(service_module, "collect_coupon_plans", fake_collect)

    service = NsdCouponService(MagicMock())
    report = await service.scan_user(101, today=date(2026, 6, 19))

    assert report.no_token is False
    paid = {(c.coupon_date, c.paid) for c in report.coupons}
    assert (date(2026, 6, 19), True) in paid
    assert (date(2026, 6, 18), False) in paid


async def test_scan_user_no_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        service_module.BotUserRepository,
        "get_token_by_telegram_id",
        AsyncMock(return_value=None),
    )
    report = await NsdCouponService(MagicMock()).scan_user(101, today=date(2026, 6, 19))
    assert report.no_token is True


async def test_scan_user_no_coupons(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service_module, "NsdClient", _FakeClient)
    monkeypatch.setattr(
        service_module.BotUserRepository,
        "get_token_by_telegram_id",
        AsyncMock(return_value="token"),
    )
    monkeypatch.setattr(
        service_module, "collect_coupon_plans", AsyncMock(return_value=[])
    )

    report = await NsdCouponService(MagicMock()).scan_user(101, today=date(2026, 6, 19))
    assert report.coupons == []
