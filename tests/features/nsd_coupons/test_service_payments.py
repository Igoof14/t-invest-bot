"""Тесты сверки выплат купонов с лентой НРД."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from features.nsd_coupons import service as service_module
from features.nsd_coupons.repository import NsdCouponTrackingRepository
from features.nsd_coupons.schemas import CouponPlan
from features.nsd_coupons.service import NsdCouponService

pytestmark = pytest.mark.usefixtures("patch_session_scope")

_FIXTURES = Path(__file__).parent / "fixtures"
_LISTING = (_FIXTURES / "search_listing.html").read_text(encoding="utf-8")
_CARD = (_FIXTURES / "card_intr.html").read_text(encoding="utf-8")


class _FakeClient:
    """Заглушка NsdClient: отдаёт сохранённые HTML списка и карточки."""

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
    )


async def test_check_payments_marks_paid_on_matching_publication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(service_module, "NsdClient", _FakeClient)
    await NsdCouponTrackingRepository.upsert_pending([_plan(1, date(2026, 6, 19))])

    service = NsdCouponService(MagicMock())
    marked = await service.check_payments(today=date(2026, 6, 19))

    assert marked == 1
    # Купон ушёл из pending (помечен paid).
    assert await NsdCouponTrackingRepository.list_pending_due(date(2026, 6, 19)) == []


async def test_check_payments_keeps_pending_on_date_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(service_module, "NsdClient", _FakeClient)
    # Плановая дата карточки — 19.06; купон на 20.06 не совпадает.
    await NsdCouponTrackingRepository.upsert_pending([_plan(1, date(2026, 6, 20))])

    service = NsdCouponService(MagicMock())
    marked = await service.check_payments(today=date(2026, 6, 19))

    assert marked == 0
    assert len(await NsdCouponTrackingRepository.list_pending_due(date(2026, 6, 20))) == 1
