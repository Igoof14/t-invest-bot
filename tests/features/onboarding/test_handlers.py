"""Тесты навигации онбординг-воронки."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message
from features.onboarding.handlers import (
    handle_nav,
    handle_token_cta,
    start_onboarding,
)
from features.onboarding.schemas import OnboardingNav
from features.onboarding.texts import STEPS
from features.users.handlers import TokenStates


def _message() -> MagicMock:
    message = MagicMock(spec=Message)
    message.answer = AsyncMock()
    message.edit_text = AsyncMock()
    message.chat = MagicMock(id=777)
    message.message_id = 1
    return message


def _callback(message: MagicMock) -> MagicMock:
    callback = MagicMock()
    callback.message = message
    callback.answer = AsyncMock()
    callback.from_user = MagicMock(id=777)
    return callback


async def test_start_onboarding_sends_first_step() -> None:
    message = _message()

    await start_onboarding(message)

    message.answer.assert_awaited_once()
    assert message.answer.await_args.args[0] == STEPS[0].text
    assert message.answer.await_args.kwargs["parse_mode"] == "HTML"
    markup = message.answer.await_args.kwargs["reply_markup"]
    labels = [b.text for row in markup.inline_keyboard for b in row]
    assert labels == ["Далее →"]


async def test_nav_advances_to_next_step() -> None:
    message = _message()
    callback = _callback(message)

    await handle_nav(callback, OnboardingNav(step=1))

    message.edit_text.assert_awaited_once()
    assert message.edit_text.await_args.args[0] == STEPS[1].text
    assert message.edit_text.await_args.kwargs["parse_mode"] == "HTML"
    callback.answer.assert_awaited_once()


async def test_nav_repeated_tap_does_not_raise() -> None:
    """Повторный тап по той же кнопке не должен ронять хендлер."""
    message = _message()
    message.edit_text.side_effect = TelegramBadRequest(
        method=None, message="Bad Request: message is not modified"
    )
    callback = _callback(message)

    await handle_nav(callback, OnboardingNav(step=1))

    callback.answer.assert_awaited_once()


async def test_nav_out_of_range_is_ignored() -> None:
    message = _message()
    callback = _callback(message)

    await handle_nav(callback, OnboardingNav(step=99))

    message.edit_text.assert_not_awaited()
    callback.answer.assert_awaited_once()


async def test_token_cta_prompts_for_token() -> None:
    message = _message()
    callback = _callback(message)
    state = MagicMock()
    state.set_state = AsyncMock()

    await handle_token_cta(callback, state)

    message.answer.assert_awaited_once()
    state.set_state.assert_awaited_once_with(TokenStates.waiting_for_token)
    callback.answer.assert_awaited_once()
