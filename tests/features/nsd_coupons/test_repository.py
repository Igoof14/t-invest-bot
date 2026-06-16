"""Тесты репозиториев подписок и трекинга купонов НРД."""

from __future__ import annotations

from datetime import date

import pytest
from features.nsd_coupons.repository import (
    NsdCouponAlertSettingsRepository,
    NsdCouponTrackingRepository,
)
from features.nsd_coupons.schemas import CouponPlan

pytestmark = pytest.mark.usefixtures("patch_session_scope")


def _plan(coupon_number: int = 1, **overrides: object) -> CouponPlan:
    data: dict[str, object] = {
        "isin": "RU000A105P23",
        "figi": "BBG00FIGI",
        "coupon_number": coupon_number,
        "coupon_date": date(2026, 6, 19),
        "amount": 0.53,
        "bond_name": "Автодор 005P-01",
        "issuer_name": 'ГК "Автодор"',
    }
    data.update(overrides)
    return CouponPlan(**data)  # type: ignore[arg-type]


async def test_toggle_creates_then_flips() -> None:
    assert await NsdCouponAlertSettingsRepository.toggle(111) is True
    assert await NsdCouponAlertSettingsRepository.is_enabled(111) is True
    assert await NsdCouponAlertSettingsRepository.toggle(111) is False
    assert await NsdCouponAlertSettingsRepository.is_enabled(111) is False


async def test_list_users_with_alerts_enabled() -> None:
    await NsdCouponAlertSettingsRepository.toggle(1)
    await NsdCouponAlertSettingsRepository.toggle(2)
    await NsdCouponAlertSettingsRepository.toggle(2)  # off

    assert await NsdCouponAlertSettingsRepository.list_users_with_alerts_enabled() == [1]


async def test_upsert_pending_skips_duplicates() -> None:
    added = await NsdCouponTrackingRepository.upsert_pending([_plan(1), _plan(2)])
    assert added == 2
    # Повторный синк той же пары (isin, coupon_number) ничего не добавляет.
    added_again = await NsdCouponTrackingRepository.upsert_pending([_plan(1), _plan(3)])
    assert added_again == 1


async def test_list_pending_due_filters_by_date() -> None:
    await NsdCouponTrackingRepository.upsert_pending(
        [
            _plan(1, coupon_date=date(2026, 6, 19)),
            _plan(2, coupon_date=date(2026, 7, 20)),
        ]
    )
    due = await NsdCouponTrackingRepository.list_pending_due(date(2026, 6, 30))
    assert [r.coupon_number for r in due] == [1]


async def test_mark_paid_excludes_from_pending() -> None:
    await NsdCouponTrackingRepository.upsert_pending([_plan(1)])
    [record] = await NsdCouponTrackingRepository.list_pending_due(date(2026, 6, 19))

    await NsdCouponTrackingRepository.mark_paid(record.id, news_id=1409937)

    assert await NsdCouponTrackingRepository.list_pending_due(date(2026, 6, 19)) == []


async def test_mark_alerted_excludes_from_pending() -> None:
    await NsdCouponTrackingRepository.upsert_pending([_plan(1)])
    [record] = await NsdCouponTrackingRepository.list_pending_due(date(2026, 6, 19))

    await NsdCouponTrackingRepository.mark_alerted(record.id)

    assert await NsdCouponTrackingRepository.list_pending_due(date(2026, 6, 19)) == []
