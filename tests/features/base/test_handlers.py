"""Тесты гейта портфельных разделов главной клавиатуры."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Message
from common.token_gate import TOKEN_REQUIRED
from features.base import handlers


@pytest.fixture
def token(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Ответ бэкенда на запрос токена. По умолчанию токен подключён."""
    get_token = AsyncMock(return_value=True)
    monkeypatch.setattr("common.token_gate.users_api.has_any_token", get_token)
    return get_token


def _message() -> MagicMock:
    message = MagicMock(spec=Message)
    message.answer = AsyncMock(return_value=MagicMock(delete=AsyncMock()))
    message.delete = AsyncMock()
    message.chat = MagicMock(id=777)
    message.from_user = MagicMock(id=777)
    return message


@pytest.mark.parametrize(
    "handler",
    [
        handlers.handle_coupons_button,
        handlers.handle_maturities_button,
        handlers.handle_offers_button,
    ],
)
async def test_portfolio_sections_require_token(handler, token: AsyncMock) -> None:
    """Без токена раздел отвечает заглушкой и не ходит за данными."""
    token.return_value = False
    message = _message()

    await handler(message)

    message.answer.assert_awaited_once_with(TOKEN_REQUIRED, parse_mode="HTML")


async def test_coupons_open_with_token(token: AsyncMock) -> None:
    message = _message()

    await handlers.handle_coupons_button(message)

    token.assert_awaited_once_with(777)
    assert message.answer.await_args.args[0] != TOKEN_REQUIRED


async def test_notifications_open_without_token(token: AsyncMock, monkeypatch) -> None:
    """Хаб уведомлений доступен без токена — там настраивается рыночный режим."""
    token.return_value = False
    render_hub = AsyncMock(return_value=("хаб", MagicMock()))
    monkeypatch.setattr(handlers, "render_hub", render_hub)
    message = _message()

    await handlers.handle_notifications_button(message)

    render_hub.assert_awaited_once_with(777)
    assert message.answer.await_args.args[0] == "хаб"
