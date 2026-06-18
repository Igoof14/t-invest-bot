"""Тесты сервиса админской рассылки."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.exceptions import TelegramForbiddenError
from features.broadcast import service as service_module
from features.broadcast.service import BroadcastService


@pytest.fixture(autouse=True)
def _no_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    """Убирает троттлинг, чтобы тесты не ждали."""
    monkeypatch.setattr(service_module, "_SEND_DELAY", 0)


def _repo(active: list[int]) -> MagicMock:
    repo = MagicMock()
    repo.get_all_active_users = AsyncMock(return_value=active)
    repo.deactivate_user = AsyncMock(return_value=True)
    return repo


async def test_broadcast_delivers_to_all() -> None:
    bot = MagicMock()
    bot.copy_message = AsyncMock()
    repo = _repo([1, 2, 3])

    result = await BroadcastService(bot, repo=repo).broadcast(from_chat_id=10, message_id=5)

    assert result.delivered == 3
    assert result.blocked == 0
    assert bot.copy_message.await_count == 3


async def test_broadcast_deactivates_blocked_user() -> None:
    bot = MagicMock()

    async def _copy(chat_id: int, from_chat_id: int, message_id: int) -> None:
        if chat_id == 2:
            raise TelegramForbiddenError(method=MagicMock(), message="bot blocked")

    bot.copy_message = AsyncMock(side_effect=_copy)
    repo = _repo([1, 2, 3])

    result = await BroadcastService(bot, repo=repo).broadcast(from_chat_id=10, message_id=5)

    assert result.delivered == 2
    assert result.blocked == 1
    repo.deactivate_user.assert_awaited_once_with(2)


async def test_broadcast_no_users_sends_nothing() -> None:
    bot = MagicMock()
    bot.copy_message = AsyncMock()
    repo = _repo([])

    result = await BroadcastService(bot, repo=repo).broadcast(from_chat_id=10, message_id=5)

    assert result == service_module.BroadcastResult()
    bot.copy_message.assert_not_awaited()
