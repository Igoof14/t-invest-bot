"""Тесты notifier'а уведомлений об изменении рейтинга."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from features.rating_nra.notifier import RatingAlertNotifier
from features.rating_nra.schemas import ChangeType, RatingChange, RatingEvent


def _change() -> RatingChange:
    return RatingChange(
        event=RatingEvent(post_id=1, url="https://x/1/", entity_name="Эмитент"),
        change_type=ChangeType.CHANGED,
    )


async def test_send_calls_bot_with_html() -> None:
    bot = MagicMock()
    bot.send_message = AsyncMock()

    result = await RatingAlertNotifier(bot).send(123, [_change()])

    assert result is True
    bot.send_message.assert_awaited_once()
    kwargs = bot.send_message.await_args.kwargs
    assert kwargs["parse_mode"] == "HTML"
    assert kwargs["disable_web_page_preview"] is True


async def test_send_empty_changes_is_noop() -> None:
    bot = MagicMock()
    bot.send_message = AsyncMock()

    result = await RatingAlertNotifier(bot).send(123, [])

    assert result is True
    bot.send_message.assert_not_awaited()


async def test_send_returns_false_on_error() -> None:
    bot = MagicMock()
    bot.send_message = AsyncMock(side_effect=RuntimeError("telegram down"))

    result = await RatingAlertNotifier(bot).send(123, [_change()])

    assert result is False
