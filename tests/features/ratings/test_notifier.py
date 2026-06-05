"""Тесты общего notifier'а уведомлений об изменении рейтинга."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from features.ratings.events import ChangeType, RatingChange, RatingEvent
from features.ratings.notifier import RatingAlertNotifier


def _change() -> RatingChange:
    return RatingChange(
        event=RatingEvent(uid="1", url="https://x/1/", entity_name="Эмитент"),
        change_type=ChangeType.CHANGED,
    )


async def test_send_calls_bot_with_html() -> None:
    bot = MagicMock()
    bot.send_message = AsyncMock()

    result = await RatingAlertNotifier(bot).send(123, "НКР", [_change()])

    assert result is True
    bot.send_message.assert_awaited_once()
    kwargs = bot.send_message.await_args.kwargs
    assert kwargs["parse_mode"] == "HTML"
    assert kwargs["disable_web_page_preview"] is True


async def test_send_empty_changes_is_noop() -> None:
    bot = MagicMock()
    bot.send_message = AsyncMock()

    assert await RatingAlertNotifier(bot).send(123, "НКР", []) is True
    bot.send_message.assert_not_awaited()


async def test_send_returns_false_on_error() -> None:
    bot = MagicMock()
    bot.send_message = AsyncMock(side_effect=RuntimeError("telegram down"))

    assert await RatingAlertNotifier(bot).send(123, "НКР", [_change()]) is False
