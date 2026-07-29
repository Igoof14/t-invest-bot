"""Тесты основной reply-клавиатуры."""

from __future__ import annotations

from core.enums import MainKeyboardButtonTexts
from features.base.keyboards import create_main_keyboard, create_new_user_keyboard


def _labels(markup) -> list[str]:
    return [button.text for row in markup.keyboard for button in row]


def test_new_user_keyboard_has_notifications() -> None:
    """Без токена уведомления приходят по рынку — настройки должны открываться."""
    assert MainKeyboardButtonTexts.NOTIFICATIONS.value in _labels(create_new_user_keyboard())


def test_new_user_keyboard_matches_main() -> None:
    """Раскладка одна: портфельные разделы отвечают заглушкой, а не прячутся."""
    assert _labels(create_new_user_keyboard()) == _labels(create_main_keyboard())
