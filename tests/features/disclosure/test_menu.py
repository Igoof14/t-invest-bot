"""Тесты секции меню «Раскрытия эмитентов»."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from core.clients.backend.notifications import DisclosureAlertSettings
from features.disclosure import menu


def _settings(enabled: bool = True, level: str = "low") -> DisclosureAlertSettings:
    return DisclosureAlertSettings(alerts_enabled=enabled, min_risk_level=level)


def _patch(monkeypatch: pytest.MonkeyPatch, settings: DisclosureAlertSettings) -> None:
    monkeypatch.setattr(
        menu.DisclosureAlertSettingsRepository, "get", AsyncMock(return_value=settings)
    )


async def test_status_badge_reflects_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, _settings(enabled=True))
    assert await menu.status_badge(111) == "Включено 🔔"


async def test_status_badge_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, _settings(enabled=False))
    assert await menu.status_badge(111) == "Выключено 🔕"


async def test_render_marks_current_level(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, _settings(enabled=True, level="high"))

    _, markup = await menu.render(111)

    buttons = [btn.text for row in markup.inline_keyboard for btn in row]
    assert "✅ Высокий и выше" in buttons
    assert "Все события" in " ".join(buttons)


async def test_disabled_section_hides_level_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    """Выключенная секция ничего не шлёт — порог у неё нерелевантен."""
    _patch(monkeypatch, _settings(enabled=False))

    _, markup = await menu.render(111)

    buttons = [btn.text for row in markup.inline_keyboard for btn in row]
    assert not any("Все события" in text for text in buttons)
