"""Тесты callback-данных настроек рейтингов."""

from __future__ import annotations

from features.ratings.schemas import RatingAlertCallback


def test_callback_pack_unpack_roundtrip() -> None:
    packed = RatingAlertCallback(action="toggle", agency="nra").pack()
    parsed = RatingAlertCallback.unpack(packed)

    assert parsed.action == "toggle"
    assert parsed.agency == "nra"


def test_callback_prefix() -> None:
    packed = RatingAlertCallback(action="toggle", agency="nra").pack()
    assert packed.startswith("rating")
