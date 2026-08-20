"""Тесты проверки токена для портфельных разделов."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from common.token_gate import has_token
from core.clients.backend.errors import BackendError, UserNotFound


@pytest.fixture
def get_token(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock = AsyncMock(return_value=True)
    monkeypatch.setattr("common.token_gate.users_api.has_any_token", mock)
    return mock


async def test_token_connected(get_token: AsyncMock) -> None:
    assert await has_token(1) is True
    get_token.assert_awaited_once_with(1)


async def test_token_absent(get_token: AsyncMock) -> None:
    get_token.return_value = False

    assert await has_token(1) is False


async def test_unknown_user_has_no_token(get_token: AsyncMock) -> None:
    get_token.side_effect = UserNotFound("нет такого")

    assert await has_token(1) is False


async def test_backend_failure_does_not_close_section(get_token: AsyncMock) -> None:
    """Сбой бэкенда не должен закрывать раздел тому, у кого токен есть."""
    get_token.side_effect = BackendError("бэкенд лёг")

    assert await has_token(1) is True
