"""Тесты записи продуктовых событий."""

from __future__ import annotations

import pytest
from features.analytics import repository as repository_module
from features.analytics.models import BotEvent
from features.analytics.repository import AnalyticsRepository
from sqlalchemy import select

pytestmark = pytest.mark.usefixtures("patch_session_scope")


async def _events() -> list[BotEvent]:
    """Читает события через подменённый на SQLite ``session_scope``."""
    async with repository_module.session_scope() as session:
        result = await session.execute(select(BotEvent).order_by(BotEvent.id))
        return list(result.scalars().all())


async def test_add_event_persists_all_fields() -> None:
    assert await AnalyticsRepository.add_event(
        "callback_click",
        direction="in",
        telegram_id=777,
        action="menu:price:open",
        latency_ms=42,
        props={"matched": True},
    )

    events = await _events()
    assert len(events) == 1
    event = events[0]
    assert event.event_name == "callback_click"
    assert event.direction == "in"
    assert event.telegram_id == 777
    assert event.action == "menu:price:open"
    assert event.latency_ms == 42
    assert event.props == {"matched": True}
    assert event.occurred_at is not None
    assert event.exported_at is None


async def test_add_event_allows_missing_user() -> None:
    """Системные события не привязаны к пользователю."""
    assert await AnalyticsRepository.add_event("broadcast_finished", direction="out")

    events = await _events()
    assert events[0].telegram_id is None


async def test_add_event_swallows_db_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Сбой БД не пробрасывается: аналитика не должна ронять хендлер."""

    def _boom() -> None:
        raise RuntimeError("db is down")

    monkeypatch.setattr("features.analytics.repository.session_scope", _boom)

    assert await AnalyticsRepository.add_event("command", direction="in") is False
