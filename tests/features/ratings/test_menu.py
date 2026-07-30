"""Тесты секции меню «Кредитные рейтинги»."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from core.clients.backend.notifications import NotificationSettings
from features.menu.callbacks import MenuCallback
from features.menu.keyboards import HUB_KEY
from features.ratings import menu
from features.ratings.enums import RatingAgency
from features.ratings.repository import RatingSubscriptions


def test_status_badge_reflects_enabled() -> None:
    hub = NotificationSettings(enabled_agencies=frozenset({RatingAgency.NRA.value}))
    assert menu.status_badge(hub) == "Включено 🔔"


def test_status_badge_when_disabled() -> None:
    assert menu.status_badge(NotificationSettings()) == "Выключено 🔕"


def test_status_badge_ignores_unknown_agency() -> None:
    """Бэкенд хранит что прислали: незнакомое значение — не подписка."""
    hub = NotificationSettings(enabled_agencies=frozenset({"unknown"}))
    assert menu.status_badge(hub) == "Выключено 🔕"


async def test_render_includes_back_button(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        menu.RatingAlertSettingsRepository,
        "get",
        AsyncMock(return_value=RatingSubscriptions(agencies=frozenset())),
    )

    text, markup = await menu.render(111)
    buttons = [btn for row in markup.inline_keyboard for btn in row]
    back = [
        b
        for b in buttons
        if b.callback_data
        and b.callback_data.startswith("menu:")
        and MenuCallback.unpack(b.callback_data).section == HUB_KEY
    ]

    assert text  # описание раздела
    assert len(back) == 1  # есть кнопка «Назад» в хаб

    help_btns = [
        b
        for b in buttons
        if b.callback_data
        and b.callback_data.startswith("menu:")
        and MenuCallback.unpack(b.callback_data).action == "help"
    ]
    assert len(help_btns) == 1  # есть кнопка «Как это работает»


async def test_section_has_help_text() -> None:
    assert menu.SECTION.help_text
