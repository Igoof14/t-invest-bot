"""Тесты репозитория пользователей.

Данные живут в бэкенде, поэтому здесь проверяется ровно то, за что репозиторий
теперь отвечает: он зовёт нужный метод API и не даёт его ошибке дойти до хендлера
(кроме регистрации — там ошибка пробрасывается).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from common.brokers import Broker
from core.clients.backend.errors import BackendError, UserNotFound
from core.clients.backend.users import Registration
from features.users.repository import BotUserRepository


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Подменяет модуль-клиент целиком: каждый метод — AsyncMock."""
    mock = AsyncMock()
    mock.register.return_value = Registration(is_new_user=True, has_token=False)
    mock.get_token.return_value = None
    mock.list_active.return_value = []
    monkeypatch.setattr("features.users.repository.users_api", mock)
    return mock


async def test_register_returns_state(api: AsyncMock) -> None:
    api.register.return_value = Registration(is_new_user=False, has_token=True)

    assert await BotUserRepository.register_and_get_state(100, username="new") == (False, True)
    api.register.assert_awaited_once_with(
        telegram_id=100, username="new", first_name=None, last_name=None
    )


async def test_register_propagates_backend_error(api: AsyncMock) -> None:
    """На `/start` показывать нечего без ответа бэкенда — ошибку ловит хендлер."""
    api.register.side_effect = BackendError("backend down")

    with pytest.raises(BackendError):
        await BotUserRepository.register_and_get_state(100)


async def test_get_token(api: AsyncMock) -> None:
    api.get_token.return_value = "t.secret"

    assert await BotUserRepository.get_token_by_telegram_id(3) == "t.secret"
    api.get_token.assert_awaited_once_with(3, Broker.TINVEST)


async def test_get_token_accepts_a_broker(api: AsyncMock) -> None:
    api.get_token.return_value = "f.secret"

    assert await BotUserRepository.get_token_by_telegram_id(3, Broker.FINAM) == "f.secret"
    api.get_token.assert_awaited_once_with(3, Broker.FINAM)


@pytest.mark.parametrize("value", [None, ""])
async def test_get_token_without_token_is_none(api: AsyncMock, value: str | None) -> None:
    api.get_token.return_value = value

    assert await BotUserRepository.get_token_by_telegram_id(3) is None


async def test_get_token_swallows_unknown_user(api: AsyncMock) -> None:
    api.get_token.side_effect = UserNotFound("нет такого")

    assert await BotUserRepository.get_token_by_telegram_id(999) is None


async def test_active_users_listing(api: AsyncMock) -> None:
    api.list_active.return_value = [10, 11]

    assert await BotUserRepository.get_all_active_users() == [10, 11]


async def test_active_users_returns_empty_on_error(api: AsyncMock) -> None:
    api.list_active.side_effect = BackendError("backend down")

    assert await BotUserRepository.get_all_active_users() == []


async def test_deactivate_user(api: AsyncMock) -> None:
    assert await BotUserRepository.deactivate_user(20) is True
    api.deactivate.assert_awaited_once_with(20)


async def test_deactivate_user_returns_false_on_error(api: AsyncMock) -> None:
    api.deactivate.side_effect = BackendError("backend down")

    assert await BotUserRepository.deactivate_user(20) is False
