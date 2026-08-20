"""Тесты клавиатур настроек: подключение — единственная кнопка, всё остальное в мини-аппе."""

from __future__ import annotations

from aiogram.types import WebAppInfo
from features.users.keyboards import (
    create_open_miniapp_keyboard,
    create_settings_keyboard,
    settings_text,
)


def _texts(has_token: bool) -> list[str]:
    markup = create_settings_keyboard(has_token).as_markup()
    return [button.text for row in markup.inline_keyboard for button in row]


def test_add_token_button_without_token() -> None:
    assert _texts(has_token=False) == ["Подключить токен"]


def test_replace_token_button_with_token() -> None:
    """С токеном кнопка меняет подпись — она заменяет, а не добавляет ещё один."""
    assert _texts(has_token=True) == ["Заменить токен"]


def test_settings_text_shows_token_status() -> None:
    """Экран объясняет свои кнопки: раньше это было просто слово «Настройки»."""
    assert "не подключён" in settings_text(False)
    assert "подключён ✅" in settings_text(True)


def test_open_miniapp_keyboard_has_web_app_and_back_buttons() -> None:
    web_app = WebAppInfo(url="https://app.example.com/profile")
    markup = create_open_miniapp_keyboard(web_app).as_markup()
    buttons = [b for row in markup.inline_keyboard for b in row]

    assert buttons[0].web_app == web_app
    assert buttons[1].text == "⬅️ Назад"
