"""Тесты общего репозитория состояния релизов рейтингов."""

from __future__ import annotations

from datetime import datetime

import pytest
from features.ratings.enums import RatingAgency
from features.ratings.events import ChangeType, RatingEvent
from features.ratings.repository import RatingReleaseRepository

pytestmark = pytest.mark.usefixtures("patch_session_scope")


def _event(uid: str = "nkr-1", **overrides: object) -> RatingEvent:
    data: dict[str, object] = {
        "uid": uid,
        "url": f"https://ratings.ru/ratings/press-releases/{uid}/",
        "inn": "5321029508",
        "rating_action": "Подтверждён",
        "rating_value": "AA.ru",
    }
    data.update(overrides)
    return RatingEvent(**data)  # type: ignore[arg-type]


async def test_upsert_and_get_seen_scoped_by_agency() -> None:
    await RatingReleaseRepository.upsert_many(RatingAgency.NKR, [_event("a"), _event("b")])
    await RatingReleaseRepository.upsert_many(RatingAgency.NRA, [_event("a")])

    seen_nkr = await RatingReleaseRepository.get_seen(RatingAgency.NKR)
    assert set(seen_nkr) == {"a", "b"}

    seen_nra = await RatingReleaseRepository.get_seen(RatingAgency.NRA)
    assert set(seen_nra) == {"a"}


async def test_upsert_stores_modified_iso() -> None:
    await RatingReleaseRepository.upsert_many(
        RatingAgency.NRA, [_event("x", modified=datetime(2026, 6, 3, 10, 8, 31))]
    )
    seen = await RatingReleaseRepository.get_seen(RatingAgency.NRA)
    assert seen["x"] == "2026-06-03T10:08:31"


def test_classify_new_changed_none() -> None:
    assert RatingReleaseRepository.classify("u", None, {}) is ChangeType.NEW
    assert (
        RatingReleaseRepository.classify("u", "2026-02-02T00:00:00", {"u": "2026-01-01T00:00:00"})
        is ChangeType.CHANGED
    )
    assert RatingReleaseRepository.classify("u", None, {"u": "2026-01-01T00:00:00"}) is None
