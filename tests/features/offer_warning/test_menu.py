"""Тесты секции меню «Напоминание об оферте»."""

from __future__ import annotations

from datetime import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from features.menu.callbacks import MenuCallback
from features.menu.keyboards import HUB_KEY
from features.offer_warning import menu


def _settings(enabled: bool) -> SimpleNamespace:
    return SimpleNamespace(
        alerts_enabled=enabled,
        first_alert=14,
        second_alert=5,
        notification_time=time(10, 0),
    )


async def test_status_badge(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        menu.OfferSettingsRepository, "get_or_create", AsyncMock(return_value=_settings(True))
    )
    assert await menu.status_badge(111) == "включено"


async def test_render_has_back_button(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        menu.OfferSettingsRepository, "get_or_create", AsyncMock(return_value=_settings(False))
    )

    text, markup = await menu.render(111)
    has_back = any(
        b.callback_data
        and b.callback_data.startswith("menu:")
        and MenuCallback.unpack(b.callback_data).section == HUB_KEY
        for row in markup.inline_keyboard
        for b in row
    )

    assert "оферт" in text.lower()
    assert has_back
