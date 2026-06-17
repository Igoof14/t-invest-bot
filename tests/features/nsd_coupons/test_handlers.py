"""Тесты хендлеров подписки на уведомления о купонах."""

from __future__ import annotations

from datetime import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Message
from features.nsd_coupons import handlers as handlers_module
from features.nsd_coupons.handlers import (
    handle_scan,
    handle_set_report_time,
    handle_toggle,
    process_report_time,
    show_settings,
)
from features.nsd_coupons.repository import NsdCouponAlertSettingsRepository
from features.nsd_coupons.schemas import CouponScanReport

pytestmark = pytest.mark.usefixtures("patch_session_scope")


def _text_message(text: str, telegram_id: int = 42) -> MagicMock:
    message = MagicMock(spec=Message)
    message.text = text
    message.chat = MagicMock(id=telegram_id)
    message.answer = AsyncMock()
    return message


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


async def test_scan_shows_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    callback = _callback(42)

    service = MagicMock()
    service.scan_user = AsyncMock(return_value=CouponScanReport())
    monkeypatch.setattr(
        handlers_module, "NsdCouponService", MagicMock(return_value=service)
    )

    await handle_scan(callback, MagicMock())

    service.scan_user.assert_awaited_once_with(42)
    # Прогресс + итоговая сводка.
    assert callback.message.edit_text.await_count == 2


async def test_scan_guards_double_run() -> None:
    handlers_module._scanning.add(42)
    try:
        callback = _callback(42)
        await handle_scan(callback, MagicMock())
        callback.message.edit_text.assert_not_awaited()
    finally:
        handlers_module._scanning.discard(42)


async def test_set_report_time_prompts_and_sets_state() -> None:
    callback = _callback(42)
    callback.message.answer = AsyncMock()
    state = MagicMock()
    state.set_state = AsyncMock()

    await handle_set_report_time(callback, state)

    callback.message.answer.assert_awaited_once()
    state.set_state.assert_awaited_once()


async def test_process_report_time_valid() -> None:
    message = _text_message("21:00", telegram_id=42)
    state = MagicMock()
    state.clear = AsyncMock()

    await process_report_time(message, state)

    assert await NsdCouponAlertSettingsRepository.get_report_time(42) == time(21, 0)
    state.clear.assert_awaited_once()


async def test_process_report_time_off() -> None:
    await NsdCouponAlertSettingsRepository.set_report_time(42, time(21, 0))
    message = _text_message("выкл", telegram_id=42)
    state = MagicMock()
    state.clear = AsyncMock()

    await process_report_time(message, state)

    assert await NsdCouponAlertSettingsRepository.get_report_time(42) is None
    state.clear.assert_awaited_once()


async def test_process_report_time_invalid_keeps_state() -> None:
    message = _text_message("99:99", telegram_id=42)
    state = MagicMock()
    state.clear = AsyncMock()

    await process_report_time(message, state)

    assert await NsdCouponAlertSettingsRepository.get_report_time(42) is None
    state.clear.assert_not_awaited()


async def test_show_settings_answers_with_keyboard() -> None:
    message = MagicMock(spec=Message)
    message.from_user = MagicMock(id=42)
    message.answer = AsyncMock()

    await show_settings(message)

    message.answer.assert_awaited_once()
    assert message.answer.await_args.kwargs["parse_mode"] == "HTML"
