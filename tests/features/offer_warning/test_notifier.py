"""Тесты отправки уведомлений об офертах."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from features.offer_warning.notifier import OfferAlertNotifier


@pytest.fixture
def bot() -> MagicMock:
    """Мок aiogram-бота с асинхронным send_message."""
    mock = MagicMock()
    mock.send_message = AsyncMock()
    return mock


async def test_send_empty_offers_returns_true_without_call(bot: MagicMock) -> None:
    notifier = OfferAlertNotifier(bot)
    result = await notifier.send(123, [])
    assert result is True
    bot.send_message.assert_not_called()


async def test_send_success_returns_true_and_calls_bot(
    bot: MagicMock, offer_factory
) -> None:
    notifier = OfferAlertNotifier(bot)
    result = await notifier.send(123, [offer_factory()])

    assert result is True
    bot.send_message.assert_awaited_once()
    args, kwargs = bot.send_message.call_args
    assert args[0] == 123
    assert kwargs["parse_mode"] == "HTML"
    assert kwargs["disable_web_page_preview"] is True


async def test_send_returns_false_on_error(bot: MagicMock, offer_factory) -> None:
    bot.send_message.side_effect = RuntimeError("network down")
    notifier = OfferAlertNotifier(bot)
    result = await notifier.send(123, [offer_factory()])
    assert result is False
