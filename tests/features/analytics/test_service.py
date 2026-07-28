"""Тесты публичного API аналитики."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from core.config import config
from features.analytics import EventName, flush_tracking, sanitize_source, track, track_bg
from features.analytics.schemas import Direction


@pytest.fixture
def add_event(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Подменяет запись в БД, чтобы проверять переданные аргументы."""
    mock = AsyncMock(return_value=True)
    monkeypatch.setattr("features.analytics.service.AnalyticsRepository.add_event", mock)
    return mock


async def test_track_passes_fields_to_repository(
    add_event: AsyncMock, enable_analytics: None
) -> None:
    await track(
        EventName.ALERT_TOGGLED,
        telegram_id=777,
        action="price",
        latency_ms=12,
        feature="price",
        enabled=True,
    )

    add_event.assert_awaited_once()
    kwargs = add_event.await_args.kwargs
    assert add_event.await_args.args[0] == "alert_toggled"
    assert kwargs["direction"] == "in"
    assert kwargs["telegram_id"] == 777
    assert kwargs["action"] == "price"
    assert kwargs["latency_ms"] == 12
    assert kwargs["props"] == {"feature": "price", "enabled": True}


async def test_track_marks_outbound_direction(
    add_event: AsyncMock, enable_analytics: None
) -> None:
    await track(
        EventName.NOTIFICATION_SENT,
        telegram_id=777,
        direction=Direction.OUT,
        kind="offer",
    )

    assert add_event.await_args.kwargs["direction"] == "out"


async def test_track_drops_none_props(add_event: AsyncMock, enable_analytics: None) -> None:
    await track(EventName.BOT_START, telegram_id=777, source=None, is_new_user=False)

    assert add_event.await_args.kwargs["props"] == {"is_new_user": False}


async def test_track_never_writes_message_text(
    add_event: AsyncMock, enable_analytics: None
) -> None:
    """Через текст сообщения проходит T-Invest токен — он не должен попасть в БД."""
    await track(
        EventName.TEXT_MESSAGE,
        telegram_id=777,
        text="t.секретный_токен",
        token="secret",
        text_len=17,
    )

    props = add_event.await_args.kwargs["props"]
    assert props == {"text_len": 17}


async def test_track_truncates_long_action(add_event: AsyncMock, enable_analytics: None) -> None:
    await track(EventName.CALLBACK_CLICK, telegram_id=777, action="x" * 500)

    assert len(add_event.await_args.kwargs["action"]) == 128


async def test_track_is_disabled_by_kill_switch(
    add_event: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "analytics_enabled", False)

    await track(EventName.BOT_START, telegram_id=777)

    add_event.assert_not_awaited()


async def test_track_skips_admin_by_default(
    add_event: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Прожатия админа искажали бы воронку и отчёт по фичам."""
    monkeypatch.setattr(config, "analytics_enabled", True)
    monkeypatch.setattr(config, "analytics_track_admin", False)
    monkeypatch.setattr(config, "admin_id", 777)

    await track(EventName.BOT_START, telegram_id=777)
    await track(EventName.BOT_START, telegram_id=778)

    assert add_event.await_count == 1
    assert add_event.await_args.kwargs["telegram_id"] == 778


async def test_track_never_raises(monkeypatch: pytest.MonkeyPatch, enable_analytics: None) -> None:
    """Ключевой инвариант: сбой аналитики не должен ломать хендлер."""
    monkeypatch.setattr(
        "features.analytics.service.AnalyticsRepository.add_event",
        AsyncMock(side_effect=RuntimeError("boom")),
    )

    assert await track(EventName.BOT_START, telegram_id=777) is None


async def test_track_bg_does_not_block_caller(
    add_event: AsyncMock, enable_analytics: None
) -> None:
    """Событие пишется, но вызывающий код не ждёт похода в БД."""
    track_bg(EventName.BOT_START, telegram_id=779)
    assert add_event.await_count == 0  # ещё не выполнилось — задача только создана

    await flush_tracking()
    assert add_event.await_count == 1
    assert add_event.await_args.kwargs["telegram_id"] == 779


async def test_flush_tracking_without_pending_tasks() -> None:
    await flush_tracking()


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("qa_test", "qa_test"),
        ("  QA-Test  ", "qa-test"),
        (";drop table--", "droptable--"),
        ("!!!", "invalid"),
        ("a" * 100, "a" * 64),
    ],
)
def test_sanitize_source(payload: str | None, expected: str | None) -> None:
    assert sanitize_source(payload) == expected
