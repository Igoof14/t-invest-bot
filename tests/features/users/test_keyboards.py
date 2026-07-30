"""Тесты клавиатуры настроек: удалять предлагаем только то, что есть."""

from __future__ import annotations

from features.users.keyboards import create_settings_keyboard, settings_text


def _texts(has_token: bool) -> list[str]:
    markup = create_settings_keyboard(has_token).as_markup()
    return [button.text for row in markup.inline_keyboard for button in row]


def test_delete_button_hidden_without_token() -> None:
    """Без токена кнопки удаления быть не должно — удалять нечего."""
    assert _texts(has_token=False) == ["Подключить токен"]


def test_delete_button_shown_with_token() -> None:
    assert _texts(has_token=True) == ["Заменить токен", "Удалить токен"]


def test_settings_text_shows_token_status() -> None:
    """Экран объясняет свои кнопки: раньше это было просто слово «Настройки»."""
    assert "не подключён" in settings_text(False)
    assert "подключён ✅" in settings_text(True)
