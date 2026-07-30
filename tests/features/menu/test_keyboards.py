"""Тесты построения хаба меню."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from aiogram.types import InlineKeyboardMarkup
from core.clients.backend.errors import BackendError
from core.clients.backend.notifications import NotificationSettings
from features.menu.callbacks import MenuCallback
from features.menu.keyboards import (
    HUB_KEY,
    HUB_STALE_NOTE,
    MARKET_MODE_NOTE,
    back_to_hub_button,
    build_help,
    build_hub,
    help_button,
    status_text,
)
from features.menu.registry import MenuSection


@pytest.fixture(autouse=True)
def user_with_token(monkeypatch):
    """По умолчанию токен подключён — хаб не добавляет подсказку о режиме.

    Без этого каждый тест хаба ходил бы в реальный бэкенд.
    """
    get_token = AsyncMock(return_value="t0ken")
    monkeypatch.setattr("features.menu.keyboards.users_api.get_token", get_token)
    return get_token


@pytest.fixture(autouse=True)
def settings(monkeypatch):
    """Настройки уведомлений — единственный источник бейджей хаба."""
    get_settings = AsyncMock(return_value=NotificationSettings())
    monkeypatch.setattr("features.menu.keyboards.notifications_api.get_settings", get_settings)
    return get_settings


def _section(key: str, *, badge: str | None = None) -> MenuSection:
    return MenuSection(
        key=key,
        title=key.title(),
        render=AsyncMock(return_value=("t", InlineKeyboardMarkup(inline_keyboard=[]))),
        status_badge=Mock(return_value=badge) if badge is not None else None,
    )


async def test_build_hub_lists_sections_with_badges() -> None:
    sections = [_section("ratings", badge="включено"), _section("price", badge="выключено")]

    _text, markup = await build_hub(111, sections)
    texts = [btn.text for row in markup.inline_keyboard for btn in row]

    assert any("Ratings" in t and "включено" in t for t in texts)
    assert any("Price" in t and "выключено" in t for t in texts)


async def test_build_hub_reads_settings_once_for_all_sections(settings) -> None:
    """Настройки читаются одним запросом: эндпоинт отдаёт все секции сразу."""
    sections = [_section(f"s{i}", badge="включено") for i in range(4)]

    _text, markup = await build_hub(111, sections)

    settings.assert_awaited_once_with(111)
    assert len([btn for row in markup.inline_keyboard for btn in row]) == 4


async def test_build_hub_survives_failing_badge() -> None:
    """Сбой одной секции не роняет весь экран — она остаётся без бейджа."""
    sections = [
        _section("ok", badge="включено"),
        MenuSection(
            key="broken",
            title="Broken",
            render=AsyncMock(return_value=("t", InlineKeyboardMarkup(inline_keyboard=[]))),
            status_badge=Mock(side_effect=RuntimeError("боль")),
        ),
    ]

    _text, markup = await build_hub(111, sections)
    texts = [btn.text for row in markup.inline_keyboard for btn in row]

    assert texts == ["Ok: включено", "Broken"]


async def test_build_hub_hides_badges_when_settings_unavailable(settings) -> None:
    """Без настроек бейджей нет ни у кого — «Выключено 🔕» было бы враньём."""
    settings.side_effect = BackendError("бэкенд лёг")
    sections = [_section("ok", badge="включено"), _section("more", badge="выключено")]

    text, markup = await build_hub(111, sections)
    texts = [btn.text for row in markup.inline_keyboard for btn in row]

    assert texts == ["Ok", "More"]
    assert HUB_STALE_NOTE in text


async def test_build_hub_without_badge() -> None:
    _text, markup = await build_hub(111, [_section("plain")])
    texts = [btn.text for row in markup.inline_keyboard for btn in row]

    assert texts == ["Plain"]


async def test_build_hub_upsells_token_when_absent(user_with_token) -> None:
    """Без токена хаб объясняет режим и предлагает его подключить."""
    user_with_token.return_value = None

    text, markup = await build_hub(111, [_section("plain")])
    texts = [btn.text for row in markup.inline_keyboard for btn in row]

    assert MARKET_MODE_NOTE in text
    assert texts == ["Plain", "Подключить токен"]


async def test_build_hub_hides_upsell_when_backend_fails(user_with_token) -> None:
    """Сбой бэкенда не должен предлагать токен тому, у кого он уже есть."""
    user_with_token.side_effect = RuntimeError("бэкенд лёг")

    text, markup = await build_hub(111, [_section("plain")])
    texts = [btn.text for row in markup.inline_keyboard for btn in row]

    assert MARKET_MODE_NOTE not in text
    assert texts == ["Plain"]


def test_status_text_shows_bell_state() -> None:
    assert status_text(True) == "Включено 🔔"
    assert status_text(False) == "Выключено 🔕"


def test_back_to_hub_button_points_to_hub() -> None:
    button = back_to_hub_button()
    parsed = MenuCallback.unpack(button.callback_data)

    assert parsed.section == HUB_KEY
    assert parsed.action == "open"


def test_help_button_uses_help_action() -> None:
    parsed = MenuCallback.unpack(help_button("ratings").callback_data)

    assert parsed.section == "ratings"
    assert parsed.action == "help"


async def test_build_help_shows_text_and_back_to_section() -> None:
    section = MenuSection(
        key="ratings",
        title="Ratings",
        render=AsyncMock(return_value=("t", InlineKeyboardMarkup(inline_keyboard=[]))),
        help_text="<b>Как это работает</b>",
    )

    text, markup = build_help(section)
    back = MenuCallback.unpack(markup.inline_keyboard[0][0].callback_data)

    assert text == "<b>Как это работает</b>"
    assert back.section == "ratings"
    assert back.action == "open"
