"""Тесты клиента бэкенда для пользователей бота."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from unittest.mock import AsyncMock

import pytest
from core.clients.backend import users


@pytest.fixture
def request_mock(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Подменяет HTTP-обвязку, оставляя проверку метода, пути и тела."""
    mock = AsyncMock(return_value={})
    monkeypatch.setattr("core.clients.backend.users.request", mock)
    return mock


def call(request_mock: AsyncMock) -> tuple[tuple[Any, ...], Mapping[str, Any]]:
    """Позиционные и именованные аргументы последнего вызова `request`."""
    await_args = request_mock.await_args
    assert await_args is not None
    return await_args.args, await_args.kwargs


async def test_register_sends_profile_fields(request_mock: AsyncMock) -> None:
    request_mock.return_value = {"is_new_user": True, "has_token": False}

    result = await users.register(42, username="alice", first_name="Alice")

    args, kwargs = call(request_mock)
    assert args == ("POST", "/api/v1/users/register")
    assert kwargs["json"] == {
        "telegram_id": 42,
        "username": "alice",
        "first_name": "Alice",
        "last_name": None,
    }
    assert (result.is_new_user, result.has_token) == (True, False)


async def test_register_defaults_missing_flags_to_false(request_mock: AsyncMock) -> None:
    result = await users.register(42)

    assert (result.is_new_user, result.has_token) == (False, False)


async def test_get_token_returns_none_when_not_connected(request_mock: AsyncMock) -> None:
    request_mock.return_value = {"token": None}

    assert await users.get_token(42) is None
    assert call(request_mock)[0] == ("GET", "/api/v1/users/42/token")


async def test_set_token_uses_put(request_mock: AsyncMock) -> None:
    await users.set_token(42, "t.secret")

    args, kwargs = call(request_mock)
    assert args == ("PUT", "/api/v1/users/42/token")
    assert kwargs["json"] == {"token": "t.secret"}


async def test_delete_token_uses_delete(request_mock: AsyncMock) -> None:
    await users.delete_token(42)

    assert call(request_mock)[0] == ("DELETE", "/api/v1/users/42/token")


async def test_deactivate_uses_post(request_mock: AsyncMock) -> None:
    await users.deactivate(42)

    assert call(request_mock)[0] == ("POST", "/api/v1/users/42/deactivate")


async def test_list_active_returns_ids(request_mock: AsyncMock) -> None:
    request_mock.return_value = {"telegram_ids": [1, 2], "count": 2}

    assert await users.list_active() == [1, 2]
    assert call(request_mock)[0] == ("GET", "/api/v1/users/active")


async def test_list_active_tolerates_missing_field(request_mock: AsyncMock) -> None:
    assert await users.list_active() == []
