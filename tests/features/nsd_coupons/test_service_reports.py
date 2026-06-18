"""Тесты ежедневной рассылки отчётов по купонам."""

from __future__ import annotations

import asyncio
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


async def test_send_report_to_sends_when_coupons() -> None:
    bot = MagicMock()
    bot.send_message = AsyncMock()
    service = NsdCouponService(bot)
    service.scan_user = AsyncMock(return_value=_report_with_coupons())

    await service._send_report_to(10, date(2026, 6, 17))

    bot.send_message.assert_awaited_once()
    assert bot.send_message.await_args.args[0] == 10


async def test_send_report_to_skips_when_no_coupons() -> None:
    bot = MagicMock()
    bot.send_message = AsyncMock()
    service = NsdCouponService(bot)
    service.scan_user = AsyncMock(return_value=CouponScanReport())

    await service._send_report_to(10, date(2026, 6, 17))

    bot.send_message.assert_not_awaited()


async def test_send_report_to_skips_when_no_token() -> None:
    bot = MagicMock()
    bot.send_message = AsyncMock()
    service = NsdCouponService(bot)
    service.scan_user = AsyncMock(return_value=CouponScanReport(no_token=True))

    await service._send_report_to(10, date(2026, 6, 17))

    bot.send_message.assert_not_awaited()


async def test_send_daily_reports_dispatches_matching() -> None:
    await NsdCouponAlertSettingsRepository.set_report_time(10, time(21, 0))
    await NsdCouponAlertSettingsRepository.set_report_time(20, time(9, 0))  # не сейчас

    service = NsdCouponService(MagicMock())
    service._send_report_to = AsyncMock()

    dispatched = await service.send_daily_reports(now=_NOW)
    # Тик возвращается мгновенно; задачи доигрываем вручную.
    await asyncio.gather(*list(service._report_tasks))

    assert dispatched == 1
    service._send_report_to.assert_awaited_once_with(10, _NOW.date())


async def test_send_daily_reports_no_recipients() -> None:
    service = NsdCouponService(MagicMock())
    service._send_report_to = AsyncMock()

    assert await service.send_daily_reports(now=_NOW) == 0
    service._send_report_to.assert_not_awaited()
