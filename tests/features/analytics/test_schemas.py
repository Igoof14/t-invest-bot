"""Тесты доменных типов аналитики."""

from __future__ import annotations

from features.analytics.schemas import Direction, EventName


def test_event_names_are_snake_case_and_match_values() -> None:
    """Имена событий читаются напрямую в SQL, поэтому формат фиксирован."""
    for event in EventName:
        assert event.value.islower()
        assert " " not in event.value
        assert event.value == event.value.strip("_")


def test_event_names_are_unique() -> None:
    assert len({e.value for e in EventName}) == len(list(EventName))


def test_directions_fit_column_width() -> None:
    """Колонка direction — String(3)."""
    for direction in Direction:
        assert len(direction.value) <= 3


def test_funnel_events_exist() -> None:
    """Воронка онбординга опирается на эти имена — они не должны исчезнуть."""
    required = {
        "bot_start",
        "onboarding_step_shown",
        "onboarding_cta_clicked",
        "token_prompt_shown",
        "token_submitted",
        "token_connected",
        "alert_toggled",
        "notification_sent",
        "notification_failed",
    }
    assert required <= {e.value for e in EventName}
