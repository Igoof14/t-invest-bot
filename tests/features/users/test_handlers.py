"""Тесты хендлеров настроек в features.users.handlers.

Добавление и удаление токена бот больше не делает сам — экран настроек только
показывает кнопку открытия мини-аппа. Здесь проверяется именно это поведение.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Message
from core.config import config
from features.users import handlers as users_handlers
from features.users.handlers import handle_add_token, handle_back_to_settings


def _callback(telegram_id: int = 777) -> MagicMock:
    """Создаёт мок нажатия инлайн-кнопки."""
    callback = MagicMock()
    callback.from_user.id = telegram_id
    callback.message = MagicMock(spec=Message)
    callback.message.chat = MagicMock(id=telegram_id)
    callback.message.answer = AsyncMock()
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    return callback


async def test_add_token_shows_miniapp_button(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "miniapp_url", "https://app.example.com")
    callback = _callback()

    await handle_add_token(callback)

    callback.message.answer.assert_awaited_once()
    markup = callback.message.answer.await_args.kwargs["reply_markup"]
    buttons = [b for row in markup.inline_keyboard for b in row]
    assert buttons[0].web_app.url == "https://app.example.com/profile"
    callback.answer.assert_awaited_once()


async def test_add_token_without_miniapp_url_explains_unavailability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "miniapp_url", None)
    callback = _callback()

    await handle_add_token(callback)

    callback.message.answer.assert_awaited_once()
    assert "reply_markup" not in callback.message.answer.await_args.kwargs
    assert "недоступно" in callback.message.answer.await_args.args[0]


async def test_back_to_settings_shows_current_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(users_handlers, "has_token", AsyncMock(return_value=True))
    callback = _callback()

    await handle_back_to_settings(callback)

    assert "подключён ✅" in callback.message.edit_text.await_args.args[0]
    callback.answer.assert_awaited_once()
