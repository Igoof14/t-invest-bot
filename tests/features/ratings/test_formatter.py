"""Тесты общего форматтера уведомлений об изменении рейтинга."""

from __future__ import annotations

from features.ratings.events import ChangeType, RatingChange, RatingEvent
from features.ratings.formatter import format_rating_alert


def _change(**event_overrides: object) -> RatingChange:
    data: dict[str, object] = {
        "uid": "1",
        "url": "https://ratings.ru/ratings/press-releases/x/",
        "entity_name": "ПАО «Акрон»",
        "rating_action": "Понижен",
        "rating_value": "AA.ru",
        "outlook": "Негативный",
    }
    data.update(event_overrides)
    return RatingChange(
        event=RatingEvent(**data),  # type: ignore[arg-type]
        change_type=ChangeType.CHANGED,
        matched_bond_names=["Акрон БО-001P-04"],
    )


def test_format_includes_core_fields_and_agency() -> None:
    message = format_rating_alert("НКР", [_change()])

    assert "НКР" in message
    assert "ПАО «Акрон»" in message
    assert "Понижен" in message
    assert "AA.ru" in message
    assert "Негативный" in message
    assert "Акрон БО-001P-04" in message


def test_format_handles_missing_entity() -> None:
    change = RatingChange(
        event=RatingEvent(uid="2", url="https://x/2/", entity_name=None),
        change_type=ChangeType.NEW,
    )
    assert "Эмитент" in format_rating_alert("НРА", [change])
