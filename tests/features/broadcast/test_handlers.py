"""Тесты хендлеров админской рассылки."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Message
from features.broadcast import handlers as handlers_module
from features.broadcast.handlers import (
    BroadcastStates,
    cancel_broadcast,
    collect_message,
    confirm_broadcast,
    start_broadcast,
)
from features.broadcast.schemas import BroadcastResult

ADMIN_ID = 100


@pytest.fixture(autouse=True)
def _set_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(handlers_module.config, "admin_id", ADMIN_ID)


def _message(user_id: int) -> MagicMock:
    message = MagicMock(spec=Message)
    message.from_user = MagicMock(id=user_id)
    message.chat = MagicMock(id=user_id)
    message.message_id = 555
    message.answer = AsyncMock()
    return message


def _state() -> MagicMock:
    state = MagicMock()
    state.set_state = AsyncMock()
    state.update_data = AsyncMock()
    state.get_data = AsyncMock(return_value={})
    state.clear = AsyncMock()
    return state


async def test_non_admin_is_ignored() -> None:
    message = _message(user_id=999)
    state = _state()

    await start_broadcast(message, state)

    state.set_state.assert_not_awaited()
    message.answer.assert_not_awaited()


async def test_admin_enters_waiting_for_message() -> None:
    message = _message(user_id=ADMIN_ID)
    state = _state()

    await start_broadcast(message, state)

    state.set_state.assert_awaited_once_with(BroadcastStates.waiting_for_message)
    message.answer.assert_awaited_once()


async def test_collect_message_shows_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        handlers_module.BotUserRepository,
        "get_all_active_users",
        AsyncMock(return_value=[1, 2]),
    )
    message = _message(user_id=ADMIN_ID)
    state = _state()

    await collect_message(message, state)

    state.update_data.assert_awaited_once_with(from_chat_id=ADMIN_ID, message_id=555)
    state.set_state.assert_awaited_once_with(BroadcastStates.waiting_for_confirmation)
    message.answer.assert_awaited_once()


async def test_confirm_runs_service_and_clears(monkeypatch: pytest.MonkeyPatch) -> None:
    service = MagicMock()
    service.broadcast = AsyncMock(return_value=BroadcastResult(delivered=2, blocked=1))
    monkeypatch.setattr(
        handlers_module, "BroadcastService", MagicMock(return_value=service)
    )
    callback = MagicMock()
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.message.answer = AsyncMock()
    callback.answer = AsyncMock()
    state = _state()
    state.get_data = AsyncMock(return_value={"from_chat_id": 5, "message_id": 7})

    await confirm_broadcast(callback, state, MagicMock())

    service.broadcast.assert_awaited_once_with(5, 7)
    state.clear.assert_awaited_once()
    callback.answer.assert_awaited_once()


async def test_cancel_clears_state() -> None:
    callback = MagicMock()
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    state = _state()

    await cancel_broadcast(callback, state)

    state.clear.assert_awaited_once()
    callback.message.edit_text.assert_awaited_once()
    callback.answer.assert_awaited_once()
