"""Тесты утилит работы с ботом."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message
from common.utils.bot_utils import safe_edit_text


def _message() -> MagicMock:
    message = MagicMock(spec=Message)
    message.message_id = 1
    message.edit_text = AsyncMock()
    return message


async def test_edit_returns_true_on_change() -> None:
    message = _message()

    assert await safe_edit_text(message, "новый текст") is True
    message.edit_text.assert_awaited_once()


async def test_repeated_tap_is_not_an_error() -> None:
    """Повторный тап по той же кнопке — нормальное поведение, не ошибка."""
    message = _message()
    message.edit_text.side_effect = TelegramBadRequest(
        method=None,
        message="Bad Request: message is not modified: specified new message content "
        "and reply markup are exactly the same as a current content and reply markup",
    )

    assert await safe_edit_text(message, "тот же текст") is False


async def test_other_bad_requests_still_raise() -> None:
    """Глушим только «не изменилось» — остальные ошибки должны быть видны."""
    message = _message()
    message.edit_text.side_effect = TelegramBadRequest(
        method=None, message="Bad Request: message to edit not found"
    )

    with pytest.raises(TelegramBadRequest):
        await safe_edit_text(message, "текст")
