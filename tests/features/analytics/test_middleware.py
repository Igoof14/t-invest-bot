"""Тесты мидлвари автоматического трекинга апдейтов."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from aiogram.dispatcher.event.bases import UNHANDLED
from aiogram.types import CallbackQuery, Chat, Message, Update, User
from features.analytics.middleware import AnalyticsMiddleware

pytestmark = pytest.mark.usefixtures("enable_analytics")


@pytest.fixture
def track(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Подменяет track и touch активности, чтобы не ходить в БД."""
    mock = AsyncMock()
    monkeypatch.setattr("features.analytics.middleware.track", mock)
    monkeypatch.setattr(
        "features.users.repository.BotUserRepository.touch_last_activity_if_stale",
        AsyncMock(return_value=True),
    )
    return mock


def _user() -> User:
    return User(id=777, is_bot=False, first_name="Тест")


def _message_update(text: str) -> Update:
    message = Message(
        message_id=1,
        date=datetime.now(UTC),
        chat=Chat(id=777, type="private"),
        from_user=_user(),
        text=text,
    )
    return Update(update_id=1, message=message)


def _callback_update(data: str) -> Update:
    callback = CallbackQuery(
        id="cb-1",
        from_user=_user(),
        chat_instance="ci",
        data=data,
    )
    return Update(update_id=2, callback_query=callback)


async def _run(update: Update, handler: Any) -> Any:
    return await AnalyticsMiddleware()(handler, update, {})


async def test_command_is_tracked_with_name(track: AsyncMock) -> None:
    await _run(_message_update("/start"), AsyncMock(return_value="done"))

    track.assert_awaited_once()
    args, kwargs = track.await_args
    assert str(args[0]) == "command"
    assert kwargs["action"] == "start"
    assert kwargs["telegram_id"] == 777
    assert kwargs["matched"] is True
    assert kwargs["latency_ms"] is not None


async def test_command_payload_is_flagged(track: AsyncMock) -> None:
    await _run(_message_update("/start qa_test"), AsyncMock(return_value="done"))

    assert track.await_args.kwargs["has_payload"] is True


async def test_command_with_bot_mention_is_normalized(track: AsyncMock) -> None:
    await _run(_message_update("/start@bondelo_bot"), AsyncMock(return_value="done"))

    assert track.await_args.kwargs["action"] == "start"


async def test_callback_is_tracked_with_full_data(track: AsyncMock) -> None:
    await _run(_callback_update("menu:price:open"), AsyncMock(return_value="done"))

    args, kwargs = track.await_args
    assert str(args[0]) == "callback_click"
    assert kwargs["action"] == "menu:price:open"


async def test_reply_button_is_recognized(track: AsyncMock) -> None:
    await _run(_message_update("Купоны"), AsyncMock(return_value="done"))

    args, kwargs = track.await_args
    assert str(args[0]) == "button_click"
    assert kwargs["action"] == "Купоны"


async def test_free_text_keeps_only_length(track: AsyncMock) -> None:
    """Текст не сохраняется: через него проходит T-Invest токен."""
    await _run(_message_update("t.секретный_токен_пользователя"), AsyncMock(return_value="done"))

    args, kwargs = track.await_args
    assert str(args[0]) == "text_message"
    assert kwargs["action"] is None
    assert kwargs["text_len"] == 30
    assert "text" not in kwargs


async def test_unmatched_update_is_marked(track: AsyncMock) -> None:
    """Апдейт без хендлера — сигнал о тупике в UX."""
    await _run(_callback_update("stale:button"), AsyncMock(return_value=UNHANDLED))

    assert track.await_args.kwargs["matched"] is False


async def test_handler_exception_propagates_and_is_recorded(track: AsyncMock) -> None:
    handler = AsyncMock(side_effect=ValueError("сломалось"))

    with pytest.raises(ValueError):
        await _run(_message_update("/start"), handler)

    track.assert_awaited_once()
    kwargs = track.await_args.kwargs
    assert kwargs["error"] is True
    assert kwargs["matched"] is False


async def test_analytics_failure_does_not_break_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    """Инвариант: сбой аналитики не влияет на результат хендлера."""
    monkeypatch.setattr(
        "features.analytics.middleware.track",
        AsyncMock(side_effect=RuntimeError("analytics down")),
    )

    result = await _run(_message_update("/start"), AsyncMock(return_value="handler result"))

    assert result == "handler result"


async def test_last_activity_is_touched(
    track: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Фикс DAU: активность двигается на любом апдейте, не только на /start."""
    touch = AsyncMock(return_value=True)
    monkeypatch.setattr(
        "features.users.repository.BotUserRepository.touch_last_activity_if_stale", touch
    )

    await _run(_callback_update("menu:hub:open"), AsyncMock(return_value="done"))

    touch.assert_awaited_once_with(777)


async def test_admin_flag_is_set(track: AsyncMock, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("features.analytics.middleware.config.admin_id", 777)

    await _run(_message_update("/broadcast"), AsyncMock(return_value="done"))

    assert track.await_args.kwargs["is_admin"] is True
