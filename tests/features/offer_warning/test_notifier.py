"""Тесты отправки уведомлений об офертах."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.exceptions import TelegramForbiddenError
from common.delivery import DeliveryOutcome
from features.offer_warning.notifier import OfferAlertNotifier


@pytest.fixture
def bot() -> MagicMock:
    """Мок aiogram-бота с асинхронным send_message."""
    mock = MagicMock()
    mock.send_message = AsyncMock()
    return mock


async def test_send_empty_offers_is_sent_without_call(bot: MagicMock) -> None:
    notifier = OfferAlertNotifier(bot)
    result = await notifier.send(123, [])
    assert result.outcome is DeliveryOutcome.SENT
    bot.send_message.assert_not_called()


async def test_send_success_returns_sent_and_calls_bot(bot: MagicMock, offer_factory) -> None:
    notifier = OfferAlertNotifier(bot)
    result = await notifier.send(123, [offer_factory()])

    assert result.is_sent
    bot.send_message.assert_awaited_once()
    args, kwargs = bot.send_message.call_args
    assert args[0] == 123
    assert kwargs["parse_mode"] == "HTML"
    assert kwargs["disable_web_page_preview"] is True


async def test_transport_error_is_retryable(bot: MagicMock, offer_factory) -> None:
    bot.send_message.side_effect = RuntimeError("network down")
    notifier = OfferAlertNotifier(bot)
    result = await notifier.send(123, [offer_factory()])
    assert result.outcome is DeliveryOutcome.RETRY
    assert result.reason == "transport"


async def test_blocked_user_deactivates_and_is_not_retryable(
    bot: MagicMock, offer_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Заблокировавший бота пользователь деактивируется, ретрай не нужен."""
    deactivate = AsyncMock(return_value=True)
    monkeypatch.setattr(
        "features.users.repository.BotUserRepository.deactivate_user",
        deactivate,
    )
    bot.send_message.side_effect = TelegramForbiddenError(method=None, message="blocked")

    result = await OfferAlertNotifier(bot).send(123, [offer_factory()])

    assert result.outcome is DeliveryOutcome.BLOCKED
    assert result.should_retry is False
    deactivate.assert_awaited_once_with(123)
