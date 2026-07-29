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
    """Галочка стоит у выбранного варианта, иконка тяжести при этом остаётся."""
    _patch(monkeypatch, _settings(enabled=True, level="high"))

    _, markup = await menu.render(111)

    buttons = [btn.text for row in markup.inline_keyboard for btn in row]
    assert "🔴 Высокий и выше ✅" in buttons
    assert "🟡 Все события" in buttons


async def test_disabled_section_hides_level_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    """Выключенная секция ничего не шлёт — порог у неё нерелевантен."""
    _patch(monkeypatch, _settings(enabled=False))

    _, markup = await menu.render(111)

    buttons = [btn.text for row in markup.inline_keyboard for btn in row]
    assert not any("Все события" in text for text in buttons)


async def test_text_states_status_and_threshold() -> None:
    """Экран сам сообщает, что включено, — не только подписи кнопок."""
    text = menu.build_text(_settings(enabled=True, level="medium"))

    assert "Статус: <b>включено</b>" in text
    assert "Текущий порог:" in text
    assert "🟠 Средний и выше" in text


async def test_text_lists_every_level_that_passes() -> None:
    """Порог — это «уровень и выше», поэтому перечисляем, что реально дойдёт."""
    text = menu.build_text(_settings(enabled=True, level="high"))

    assert "Высокий риск" in text
    assert "Критический риск" in text
    assert "Средний риск" not in text


async def test_text_for_disabled_section_shows_no_threshold() -> None:
    text = menu.build_text(_settings(enabled=False))

    assert "Статус: <b>выключено</b>" in text
    assert "Текущий порог" not in text


async def test_text_survives_an_unknown_level() -> None:
    """Шкалу задаёт воркер и может расширить её без изменений в боте."""
    text = menu.build_text(_settings(enabled=True, level="catastrophic"))

    assert "catastrophic" in text
