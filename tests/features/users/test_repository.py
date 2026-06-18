"""Тесты репозитория пользователей (in-memory SQLite через session_scope)."""

from __future__ import annotations

import pytest
from features.users.repository import BotUserRepository

pytestmark = pytest.mark.usefixtures("patch_session_scope")


async def test_add_user_returns_true_for_new_then_false_for_existing() -> None:
    assert await BotUserRepository.add_user(1, username="alice") is True
    # Повторный вызов для того же пользователя только обновляет активность.
    assert await BotUserRepository.add_user(1, username="alice") is False


async def test_has_user_reflects_existence() -> None:
    assert await BotUserRepository.has_user(2) is False
    await BotUserRepository.add_user(2)
    assert await BotUserRepository.has_user(2) is True


async def test_token_lifecycle() -> None:
    await BotUserRepository.add_user(3)
    assert await BotUserRepository.has_token(3) is False

    assert await BotUserRepository.add_token(3, "t.secret") is True
    assert await BotUserRepository.has_token(3) is True
    assert await BotUserRepository.get_token_by_telegram_id(3) == "t.secret"

    assert await BotUserRepository.remove_token(3) is True
    assert await BotUserRepository.has_token(3) is False


async def test_add_token_returns_false_for_unknown_user() -> None:
    assert await BotUserRepository.add_token(999, "t.secret") is False


async def test_get_token_returns_none_for_unknown_user() -> None:
    assert await BotUserRepository.get_token_by_telegram_id(999) is None


async def test_active_users_listing_and_count() -> None:
    await BotUserRepository.add_user(10)
    await BotUserRepository.add_user(11)
    assert set(await BotUserRepository.get_all_active_users()) == {10, 11}
    assert await BotUserRepository.get_user_count() == 2


async def test_deactivate_excludes_user_from_active() -> None:
    await BotUserRepository.add_user(20)
    assert await BotUserRepository.deactivate_user(20) is True
    assert await BotUserRepository.has_user(20) is False
    assert await BotUserRepository.get_all_active_users() == []


async def test_update_last_activity_unknown_user_returns_false() -> None:
    assert await BotUserRepository.update_last_activity(999) is False
