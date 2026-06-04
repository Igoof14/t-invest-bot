"""Тесты реестра секций меню."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from aiogram.types import InlineKeyboardMarkup
from features.menu import registry


@pytest.fixture(autouse=True)
def _clean_registry() -> None:
    """Очищает реестр перед каждым тестом."""
    registry._SECTIONS.clear()


def _section(key: str) -> registry.MenuSection:
    return registry.MenuSection(
        key=key,
        title=key.title(),
        render=AsyncMock(return_value=("text", InlineKeyboardMarkup(inline_keyboard=[]))),
    )


def test_register_and_get_sections_preserves_order() -> None:
    registry.register_section(_section("a"))
    registry.register_section(_section("b"))

    assert [s.key for s in registry.get_sections()] == ["a", "b"]


def test_register_is_idempotent_by_key() -> None:
    registry.register_section(_section("a"))
    registry.register_section(_section("a"))

    assert len(registry.get_sections()) == 1


def test_get_section_by_key() -> None:
    registry.register_section(_section("a"))

    assert registry.get_section("a") is not None
    assert registry.get_section("missing") is None
