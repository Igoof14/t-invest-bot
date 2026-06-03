"""Тесты репозитория состояния полинга рейтингов НРА."""

from __future__ import annotations

from datetime import datetime

import pytest
from features.rating_nra.repository import NraReleaseRepository
from features.rating_nra.schemas import ChangeType, RatingEvent

pytestmark = pytest.mark.usefixtures("patch_session_scope")


def _event(**overrides: object) -> RatingEvent:
    data: dict[str, object] = {
        "post_id": 42241,
        "url": "https://www.ra-national.ru/press_release/test/42241/",
        "inn": "7744002652",
        "rating_action": "ПОНИЖЕН",
        "rating_value": "BBB|ru|",
        "modified": datetime(2026, 6, 3, 10, 8, 31),
    }
    data.update(overrides)
    return RatingEvent(**data)  # type: ignore[arg-type]


async def test_upsert_many_then_modified_map() -> None:
    await NraReleaseRepository.upsert_many([_event()])

    known = await NraReleaseRepository.get_modified_map()
    assert known == {42241: "2026-06-03T10:08:31"}


async def test_upsert_many_updates_existing_modified() -> None:
    await NraReleaseRepository.upsert_many([_event()])
    await NraReleaseRepository.upsert_many(
        [_event(modified=datetime(2026, 6, 4, 12, 0, 0))]
    )

    assert await NraReleaseRepository.count() == 1
    known = await NraReleaseRepository.get_modified_map()
    assert known[42241] == "2026-06-04T12:00:00"


async def test_upsert_many_empty_is_noop() -> None:
    await NraReleaseRepository.upsert_many([])
    assert await NraReleaseRepository.count() == 0


def test_classify_new_when_unknown() -> None:
    assert NraReleaseRepository.classify(1, "2026-01-01T00:00:00", {}) is ChangeType.NEW


def test_classify_changed_when_modified_differs() -> None:
    known = {1: "2026-01-01T00:00:00"}
    result = NraReleaseRepository.classify(1, "2026-02-02T00:00:00", known)
    assert result is ChangeType.CHANGED


def test_classify_none_when_modified_matches() -> None:
    known = {1: "2026-01-01T00:00:00"}
    assert NraReleaseRepository.classify(1, "2026-01-01T00:00:00", known) is None


def test_classify_none_when_known_and_modified_missing() -> None:
    known = {1: "2026-01-01T00:00:00"}
    assert NraReleaseRepository.classify(1, None, known) is None
