"""Тесты секции меню «Мониторинг цен»."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from features.menu.callbacks import MenuCallback
from features.menu.keyboards import HUB_KEY
from features.price_monitoring import menu


def _settings(enabled: bool) -> SimpleNamespace:
    return SimpleNamespace(
        alerts_enabled=enabled,
        drop_warning_threshold=2.0,
        drop_critical_threshold=5.0,
        rise_warning_threshold=3.0,
        rise_critical_threshold=7.0,
        stale=False,
    )


async def test_status_badge_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        menu.AlertSettingsRepository, "get", AsyncMock(return_value=_settings(False))
    )
    assert await menu.status_badge(111) == "Выключено 🔕"


async def test_render_has_back_button_and_thresholds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        menu.AlertSettingsRepository, "get", AsyncMock(return_value=_settings(True))
    )

    text, markup = await menu.render(111)
    has_back = any(
        b.callback_data
        and b.callback_data.startswith("menu:")
        and MenuCallback.unpack(b.callback_data).section == HUB_KEY
        for row in markup.inline_keyboard
        for b in row
    )

    assert "пороги" in text.lower()
    assert has_back
