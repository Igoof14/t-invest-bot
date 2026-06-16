"""Тесты дедлайн-проверки купонов (рассылка уведомлений о невыплате)."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from features.nsd_coupons.repository import NsdCouponTrackingRepository
from features.nsd_coupons.schemas import CouponPlan
from features.nsd_coupons.service import NsdCouponService

pytestmark = pytest.mark.usefixtures("patch_session_scope")


def _plan(coupon_date: date) -> CouponPlan:
    return CouponPlan(
        isin="RU000A105P23",
        figi="FG",
        coupon_number=1,
        coupon_date=coupon_date,
        bond_name="Автодор",
    )


async def test_check_deadlines_alerts_holders_and_marks() -> None:
    await NsdCouponTrackingRepository.upsert_pending([_plan(date(2026, 6, 19))])

    service = NsdCouponService(MagicMock())
    service._notifier = MagicMock()
    service._notifier.send = AsyncMock(return_value=True)
    service._holders_by_isin = {"RU000A105P23": {10, 20}}

    alerted = await service.check_deadlines(today=date(2026, 6, 19))

    assert alerted == 1
    assert service._notifier.send.await_count == 2
    # Купон помечен alerted → больше не в pending.
    assert await NsdCouponTrackingRepository.list_pending_due(date(2026, 6, 19)) == []


async def test_check_deadlines_ignores_not_yet_due() -> None:
    await NsdCouponTrackingRepository.upsert_pending([_plan(date(2026, 6, 25))])

    service = NsdCouponService(MagicMock())
    service._notifier = MagicMock()
    service._notifier.send = AsyncMock(return_value=True)
    service._holders_by_isin = {"RU000A105P23": {10}}

    alerted = await service.check_deadlines(today=date(2026, 6, 19))

    assert alerted == 0
    service._notifier.send.assert_not_awaited()
