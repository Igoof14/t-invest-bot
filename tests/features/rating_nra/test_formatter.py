"""Тесты форматтера уведомлений об изменении рейтинга."""

from __future__ import annotations

from features.rating_nra.formatter import format_rating_alert
from features.rating_nra.schemas import ChangeType, RatingChange, RatingEvent


def _change(**event_overrides: object) -> RatingChange:
    data: dict[str, object] = {
        "post_id": 1,
        "url": "https://www.ra-national.ru/press_release/test/1/",
        "entity_name": "ООО «Оил Ресурс»",
        "rating_action": "Понижен",
        "rating_value": "BBB-|ru|",
        "outlook": "Негативный",
    }
    data.update(event_overrides)
    return RatingChange(
        event=RatingEvent(**data),  # type: ignore[arg-type]
        change_type=ChangeType.CHANGED,
        matched_bond_names=["Оил Ресурс 1Р"],
    )


def test_format_includes_core_fields() -> None:
    message = format_rating_alert([_change()])

    assert "ООО «Оил Ресурс»" in message
    assert "Понижен" in message
    assert "BBB-|ru|" in message
    assert "Негативный" in message
    assert "Оил Ресурс 1Р" in message
    assert 'href="https://www.ra-national.ru/press_release/test/1/"' in message


def test_format_multiple_changes() -> None:
    message = format_rating_alert(
        [_change(entity_name="Эмитент А"), _change(entity_name="Эмитент Б")]
    )

    assert "Эмитент А" in message
    assert "Эмитент Б" in message


def test_format_handles_missing_optional_fields() -> None:
    change = RatingChange(
        event=RatingEvent(post_id=2, url="https://x/2/", entity_name=None),
        change_type=ChangeType.NEW,
    )
    message = format_rating_alert([change])

    assert "Эмитент" in message  # дефолтное имя
