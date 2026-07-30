"""Тесты секции меню «Блокировки счетов ФНС»."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from core.clients.backend.notifications import FnsAlertSettings, NotificationSettings
from features.fns_monitoring import menu
from features.menu.callbacks import MenuCallback
from features.menu.keyboards import HUB_KEY


def test_status_badge_reflects_enabled() -> None:
    assert menu.status_badge(NotificationSettings(fns_enabled=True)) == "Включено 🔔"


def test_status_badge_when_disabled() -> None:
    assert menu.status_badge(NotificationSettings()) == "Выключено 🔕"


async def test_render_includes_back_button(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        menu.FnsAlertSettingsRepository,
        "get",
        AsyncMock(return_value=FnsAlertSettings(alerts_enabled=False)),
    )

    text, markup = await menu.render(111)
    has_back = any(
        b.callback_data
        and b.callback_data.startswith("menu:")
        and MenuCallback.unpack(b.callback_data).section == HUB_KEY
        for row in markup.inline_keyboard
        for b in row
    )

    assert "Статус: <b>выключено</b>" in text
    assert has_back
