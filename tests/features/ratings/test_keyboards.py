"""Тесты клавиатуры настроек рейтингов."""

from __future__ import annotations

from features.ratings.enums import RatingAgency
from features.ratings.keyboards import create_rating_alerts_keyboard


def _button_texts(enabled: set[RatingAgency]) -> list[str]:
    markup = create_rating_alerts_keyboard(enabled).as_markup()
    return [btn.text for row in markup.inline_keyboard for btn in row]


def test_disabled_agency_shows_cross() -> None:
    texts = _button_texts(set())
    assert any(t == "❌ НРА" for t in texts)


def test_enabled_agency_shows_check() -> None:
    texts = _button_texts({RatingAgency.NRA})
    assert any(t == "✅ НРА" for t in texts)


def test_one_button_per_available_agency() -> None:
    from features.ratings.enums import AVAILABLE_AGENCIES

    assert len(_button_texts(set())) == len(AVAILABLE_AGENCIES)
