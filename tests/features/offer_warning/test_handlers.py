"""Тесты обработчиков и FSM уведомлений об офертах."""

from __future__ import annotations

from datetime import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Message
from features.offer_warning import handlers
from features.offer_warning.handlers import (
    OfferAlertStates,
    handle_set_settings,
    process_first_alert,
    process_second_alert,
    process_time_alert,
)
from features.offer_warning.schemas import OfferAlertCallback


def _message(text: str, chat_id: int = 555) -> MagicMock:
    """Создаёт мок входящего сообщения."""
    msg = MagicMock()
    msg.text = text
    msg.chat.id = chat_id
    msg.answer = AsyncMock()
    msg.delete = AsyncMock()
    return msg


@pytest.fixture
def state() -> MagicMock:
    """Мок FSM-контекста."""
    fsm = MagicMock()
    fsm.set_state = AsyncMock()
    fsm.clear = AsyncMock()
    return fsm


# --- process_first_alert -----------------------------------------------------


async def test_first_alert_rejects_non_digit(
    monkeypatch: pytest.MonkeyPatch, state: MagicMock
) -> None:
    update = AsyncMock()
    monkeypatch.setattr(handlers.OfferSettingsRepository, "update", update)
    msg = _message("abc")
    await process_first_alert(msg, state)
    msg.answer.assert_awaited_once()
    update.assert_not_called()
    state.clear.assert_not_called()


@pytest.mark.parametrize("value", ["0", "51"])
async def test_first_alert_rejects_out_of_range(
    monkeypatch: pytest.MonkeyPatch, state: MagicMock, value: str
) -> None:
    update = AsyncMock()
    monkeypatch.setattr(handlers.OfferSettingsRepository, "update", update)
    msg = _message(value)
    await process_first_alert(msg, state)
    update.assert_not_called()


async def test_first_alert_saves_valid_value(
    monkeypatch: pytest.MonkeyPatch, state: MagicMock
) -> None:
    update = AsyncMock()
    monkeypatch.setattr(handlers.OfferSettingsRepository, "update", update)
    msg = _message("20")
    await process_first_alert(msg, state)
    update.assert_awaited_once_with(555, first_alert=20)
    state.clear.assert_awaited_once()


# --- process_second_alert ----------------------------------------------------


async def test_second_alert_rejects_non_digit(
    monkeypatch: pytest.MonkeyPatch, state: MagicMock
) -> None:
    update = AsyncMock()
    monkeypatch.setattr(handlers.OfferSettingsRepository, "update", update)
    await process_second_alert(_message("x"), state)
    update.assert_not_called()


async def test_second_alert_saves_valid_value(
    monkeypatch: pytest.MonkeyPatch, state: MagicMock
) -> None:
    update = AsyncMock()
    monkeypatch.setattr(handlers.OfferSettingsRepository, "update", update)
    await process_second_alert(_message("5"), state)
    update.assert_awaited_once_with(555, second_alert=5)
    state.clear.assert_awaited_once()


# --- process_time_alert ------------------------------------------------------


async def test_time_alert_rejects_bad_format(
    monkeypatch: pytest.MonkeyPatch, state: MagicMock
) -> None:
    update = AsyncMock()
    monkeypatch.setattr(handlers.OfferSettingsRepository, "update", update)
    await process_time_alert(_message("25:99"), state)
    update.assert_not_called()
    state.clear.assert_not_called()


async def test_time_alert_saves_valid_time(
    monkeypatch: pytest.MonkeyPatch, state: MagicMock
) -> None:
    update = AsyncMock()
    monkeypatch.setattr(handlers.OfferSettingsRepository, "update", update)
    await process_time_alert(_message("09:30"), state)
    update.assert_awaited_once_with(555, notification_time=time(9, 30))
    state.clear.assert_awaited_once()


# --- handle_set_settings -----------------------------------------------------


@pytest.mark.parametrize(
    ("action", "expected_state"),
    [
        ("set_first", OfferAlertStates.waiting_for_first),
        ("set_second", OfferAlertStates.waiting_for_second),
        ("set_time", OfferAlertStates.waiting_for_time),
    ],
)
async def test_handle_set_settings_sets_state(
    state: MagicMock, action: str, expected_state: object
) -> None:
    callback = MagicMock()
    callback.message = MagicMock(spec=Message)
    callback.message.answer = AsyncMock()
    callback.answer = AsyncMock()
    callback_data = OfferAlertCallback(action=action)  # type: ignore[arg-type]

    await handle_set_settings(callback, callback_data, state)

    state.set_state.assert_awaited_once_with(expected_state)


# --- handle_toggle_alerts ----------------------------------------------------


async def test_handle_toggle_enabled_edits_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        handlers.OfferSettingsRepository,
        "toggle_alerts",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        handlers.OfferSettingsRepository,
        "get",
        AsyncMock(
            return_value=SimpleNamespace(
                alerts_enabled=True,
                first_alert=14,
                second_alert=5,
                notification_time=time(10, 0),
            )
        ),
    )
    callback = MagicMock()
    callback.from_user.id = 555
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()

    await handlers.handle_toggle_alerts(callback, OfferAlertCallback(action="toggle"))

    callback.message.edit_text.assert_awaited_once()
    text = callback.message.edit_text.call_args.args[0]
    assert "включен" in text
    callback.answer.assert_awaited_once()
