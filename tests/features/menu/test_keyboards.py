"""Тесты построения хаба меню."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock

import pytest
from aiogram.types import InlineKeyboardMarkup
from features.menu.callbacks import MenuCallback
from features.menu.keyboards import (
    HUB_KEY,
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


def _section(key: str, *, badge: str | None = None) -> MenuSection:
    return MenuSection(
        key=key,
        title=key.title(),
        render=AsyncMock(return_value=("t", InlineKeyboardMarkup(inline_keyboard=[]))),
        status_badge=AsyncMock(return_value=badge) if badge is not None else None,
    )


async def test_build_hub_lists_sections_with_badges() -> None:
    sections = [_section("ratings", badge="включено"), _section("price", badge="выключено")]

    _text, markup = await build_hub(111, sections)
    texts = [btn.text for row in markup.inline_keyboard for btn in row]

    assert any("Ratings" in t and "включено" in t for t in texts)
    assert any("Price" in t and "выключено" in t for t in texts)


async def test_build_hub_queries_badges_in_parallel() -> None:
    """Бейджи не должны выстраиваться в очередь: суммарное время ≈ времени одного."""

    async def slow_badge(_telegram_id: int) -> str:
        await asyncio.sleep(0.05)
        return "включено"

    sections = [
        MenuSection(
            key=f"s{i}",
            title=f"S{i}",
            render=AsyncMock(return_value=("t", InlineKeyboardMarkup(inline_keyboard=[]))),
            status_badge=slow_badge,
        )
        for i in range(4)
    ]

    started = time.perf_counter()
    _text, markup = await build_hub(111, sections)
    elapsed = time.perf_counter() - started

    assert elapsed < 0.15, f"бейджи запрашиваются последовательно: {elapsed:.3f}s"
    assert len([btn for row in markup.inline_keyboard for btn in row]) == 4


async def test_build_hub_survives_failing_badge() -> None:
    """Сбой одной секции не роняет весь экран — она остаётся без бейджа."""
    sections = [
        _section("ok", badge="включено"),
        MenuSection(
            key="broken",
            title="Broken",
            render=AsyncMock(return_value=("t", InlineKeyboardMarkup(inline_keyboard=[]))),
            status_badge=AsyncMock(side_effect=RuntimeError("боль")),
        ),
    ]

    _text, markup = await build_hub(111, sections)
    texts = [btn.text for row in markup.inline_keyboard for btn in row]

    assert texts == ["Ok: включено", "Broken"]


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
