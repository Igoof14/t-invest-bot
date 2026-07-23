"""Тесты обработчика сохранения токена в features.users.handlers."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from features.users import handlers as users_handlers
from features.users.handlers import handle_token_message


def _message(text: str, chat_id: int = 777) -> MagicMock:
    """Создаёт мок входящего сообщения."""
    msg = MagicMock()
    msg.text = text
    msg.chat.id = chat_id
    msg.answer = AsyncMock()
    return msg


@pytest.fixture
def state() -> MagicMock:
    """Мок FSM-контекста."""
    fsm = MagicMock()
    fsm.set_state = AsyncMock()
    fsm.clear = AsyncMock()
    return fsm


async def test_valid_token_schedules_bonds_sync(
    monkeypatch: pytest.MonkeyPatch, state: MagicMock
) -> None:
    monkeypatch.setattr(users_handlers, "check_token", AsyncMock(return_value=True))
    monkeypatch.setattr(users_handlers.BotUserRepository, "add_token", AsyncMock(return_value=True))
    sync_user_bonds = AsyncMock(return_value=True)
    monkeypatch.setattr(users_handlers, "sync_user_bonds", sync_user_bonds)

    await handle_token_message(_message("t.valid"), state)
    # Даём фоновой asyncio.Task шанс выполниться до проверки вызова.
    await asyncio.sleep(0)

    sync_user_bonds.assert_awaited_once_with(777)
    state.clear.assert_awaited_once()


async def test_invalid_token_does_not_schedule_sync(
    monkeypatch: pytest.MonkeyPatch, state: MagicMock
) -> None:
    monkeypatch.setattr(users_handlers, "check_token", AsyncMock(return_value=False))
    add_token = AsyncMock()
    monkeypatch.setattr(users_handlers.BotUserRepository, "add_token", add_token)
    sync_user_bonds = AsyncMock()
    monkeypatch.setattr(users_handlers, "sync_user_bonds", sync_user_bonds)

    await handle_token_message(_message("t.invalid"), state)

    add_token.assert_not_called()
    sync_user_bonds.assert_not_called()


async def test_save_failure_does_not_schedule_sync(
    monkeypatch: pytest.MonkeyPatch, state: MagicMock
) -> None:
    monkeypatch.setattr(users_handlers, "check_token", AsyncMock(return_value=True))
    monkeypatch.setattr(
        users_handlers.BotUserRepository, "add_token", AsyncMock(return_value=False)
    )
    sync_user_bonds = AsyncMock()
    monkeypatch.setattr(users_handlers, "sync_user_bonds", sync_user_bonds)

    await handle_token_message(_message("t.valid"), state)

    sync_user_bonds.assert_not_called()
