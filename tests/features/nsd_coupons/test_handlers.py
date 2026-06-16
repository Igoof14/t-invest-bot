"""Тесты хендлеров подписки на уведомления о купонах."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Message
from features.nsd_coupons.handlers import handle_toggle, show_settings
from features.nsd_coupons.repository import NsdCouponAlertSettingsRepository

pytestmark = pytest.mark.usefixtures("patch_session_scope")


def _callback(telegram_id: int) -> MagicMock:
    callback = MagicMock()
    callback.from_user.id = telegram_id
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    return callback


async def test_toggle_enables_then_updates_keyboard() -> None:
    callback = _callback(42)

    await handle_toggle(callback)

    assert await NsdCouponAlertSettingsRepository.is_enabled(42) is True
    callback.message.edit_text.assert_awaited_once()
    callback.answer.assert_awaited_once()


async def test_show_settings_answers_with_keyboard() -> None:
    message = MagicMock(spec=Message)
    message.from_user = MagicMock(id=42)
    message.answer = AsyncMock()

    await show_settings(message)

    message.answer.assert_awaited_once()
    assert message.answer.await_args.kwargs["parse_mode"] == "HTML"
