"""Тесты синка купонного календаря в сервисе."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from features.nsd_coupons import service as service_module
from features.nsd_coupons.repository import NsdCouponAlertSettingsRepository
from features.nsd_coupons.schemas import CouponPlan
from features.nsd_coupons.service import NsdCouponService

pytestmark = pytest.mark.usefixtures("patch_session_scope")


def _plan(isin: str, number: int = 1) -> CouponPlan:
    return CouponPlan(
        isin=isin,
        figi="FG",
        coupon_number=number,
        coupon_date=date(2026, 6, 19),
        amount=1.0,
    )


async def test_sync_calendar_upserts_and_builds_holders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await NsdCouponAlertSettingsRepository.toggle(1)
    await NsdCouponAlertSettingsRepository.toggle(2)

    async def fake_collect(telegram_id: int, *a: object, **k: object) -> list[CouponPlan]:
        if telegram_id == 1:
            return [_plan("RU000A105P23")]
        return [_plan("RU000A105P23"), _plan("RU000A0JX0J2")]

    monkeypatch.setattr(service_module, "collect_coupon_plans", fake_collect)

    service = NsdCouponService(MagicMock())
    added = await service.sync_calendar()

    # Уникальных пар (isin, coupon_number): две → две записи в трекинге.
    assert added == 2
    assert service._holders_by_isin["RU000A105P23"] == {1, 2}
    assert service._holders_by_isin["RU000A0JX0J2"] == {2}


async def test_sync_calendar_no_subscribers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        service_module, "collect_coupon_plans", AsyncMock(return_value=[])
    )
    service = NsdCouponService(MagicMock())
    assert await service.sync_calendar() == 0
    assert service._holders_by_isin == {}
