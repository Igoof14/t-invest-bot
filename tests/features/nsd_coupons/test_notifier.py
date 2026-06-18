"""Тесты отправки уведомления о невыплаченном купоне."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

from features.nsd_coupons.notifier import NsdCouponNotifier
from features.nsd_coupons.schemas import CouponMissAlert

_ALERT = CouponMissAlert(
    isin="RU000A105P23",
    bond_name="Автодор",
    issuer_name=None,
    coupon_number=7,
    coupon_date=date(2026, 6, 19),
    amount=12.5,
)


async def test_send_success() -> None:
    bot = MagicMock()
    bot.send_message = AsyncMock()
    notifier = NsdCouponNotifier(bot)

    assert await notifier.send(555, _ALERT) is True
    bot.send_message.assert_awaited_once()
    assert bot.send_message.await_args.kwargs["parse_mode"] == "HTML"


async def test_send_handles_failure() -> None:
    bot = MagicMock()
    bot.send_message = AsyncMock(side_effect=RuntimeError("blocked"))
    notifier = NsdCouponNotifier(bot)

    assert await notifier.send(555, _ALERT) is False
