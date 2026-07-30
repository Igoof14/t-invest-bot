"""Тесты мидлвари сброса FSM при выходе в главное меню."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from common.fsm_reset import FsmResetMiddleware


def _message(text: str) -> MagicMock:
    msg = MagicMock(spec=Message)
    msg.text = text
    msg.chat = MagicMock()
    msg.chat.id = 42
    return msg


def _state(current: str | None) -> MagicMock:
    state = MagicMock(spec=FSMContext)
    state.get_state = AsyncMock(return_value=current)
    state.clear = AsyncMock()
    return state


@pytest.mark.parametrize("text", ["Купоны", "Настройки", "Уведомления", "/start"])
async def test_menu_exit_clears_state(text: str) -> None:
    """Уход в главное меню завершает пошаговый ввод."""
    state = _state("TokenStates:waiting_for_token")
    handler = AsyncMock()

    await FsmResetMiddleware()(handler, _message(text), {"state": state})

    state.clear.assert_awaited_once()
    handler.assert_awaited_once()


async def test_arbitrary_text_keeps_state() -> None:
    """Обычный ввод внутри состояния трогать нельзя — это и есть ответ."""
    state = _state("TokenStates:waiting_for_token")

    await FsmResetMiddleware()(AsyncMock(), _message("t.abcdef"), {"state": state})

    state.clear.assert_not_called()


async def test_no_state_means_nothing_to_clear() -> None:
    state = _state(None)

    await FsmResetMiddleware()(AsyncMock(), _message("/start"), {"state": state})

    state.clear.assert_not_called()


async def test_handler_runs_without_state_in_data() -> None:
    """Мидлварь не должна ронять апдейты, у которых нет FSM-контекста."""
    handler = AsyncMock()

    await FsmResetMiddleware()(handler, _message("/start"), {})

    handler.assert_awaited_once()
