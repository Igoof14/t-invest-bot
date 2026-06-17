"""Тесты ежедневной рассылки отчётов по купонам."""

from __future__ import annotations

from datetime import date, datetime, time
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import pytest
from features.nsd_coupons.repository import NsdCouponAlertSettingsRepository
from features.nsd_coupons.schemas import CouponScanReport, ScannedCoupon
from features.nsd_coupons.service import NsdCouponService

pytestmark = pytest.mark.usefixtures("patch_session_scope")

_MSK = ZoneInfo("Europe/Moscow")
_NOW = datetime(2026, 6, 17, 21, 0, tzinfo=_MSK)


def _report_with_coupons() -> CouponScanReport:
    return CouponScanReport(
        coupons=[ScannedCoupon("RU000A105P23", "Автодор", date(2026, 6, 17), paid=False)]
    )


async def test_send_reports_to_matching_user() -> None:
    await NsdCouponAlertSettingsRepository.set_report_time(10, time(21, 0))
    await NsdCouponAlertSettingsRepository.set_report_time(20, time(9, 0))  # не сейчас

    bot = MagicMock()
    bot.send_message = AsyncMock()
    service = NsdCouponService(bot)
    service.scan_user = AsyncMock(return_value=_report_with_coupons())

    sent = await service.send_daily_reports(now=_NOW)

    assert sent == 1
    bot.send_message.assert_awaited_once()
    assert bot.send_message.await_args.args[0] == 10


async def test_skip_when_no_coupons() -> None:
    await NsdCouponAlertSettingsRepository.set_report_time(10, time(21, 0))

    bot = MagicMock()
    bot.send_message = AsyncMock()
    service = NsdCouponService(bot)
    service.scan_user = AsyncMock(return_value=CouponScanReport())  # пусто

    sent = await service.send_daily_reports(now=_NOW)

    assert sent == 0
    bot.send_message.assert_not_awaited()


async def test_skip_when_no_token() -> None:
    await NsdCouponAlertSettingsRepository.set_report_time(10, time(21, 0))

    bot = MagicMock()
    bot.send_message = AsyncMock()
    service = NsdCouponService(bot)
    service.scan_user = AsyncMock(return_value=CouponScanReport(no_token=True))

    assert await service.send_daily_reports(now=_NOW) == 0
    bot.send_message.assert_not_awaited()


async def test_no_recipients_returns_zero() -> None:
    service = NsdCouponService(MagicMock())
    service.scan_user = AsyncMock()
    assert await service.send_daily_reports(now=_NOW) == 0
    service.scan_user.assert_not_awaited()
