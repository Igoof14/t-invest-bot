"""Тесты callback-данных уведомлений об офертах."""

from __future__ import annotations

import pytest
from features.offer_warning.schemas import OfferAlertCallback


@pytest.mark.parametrize(
    "action",
    ["toggle", "setting", "set_first", "set_second", "set_time"],
)
def test_callback_pack_unpack_roundtrip(action: str) -> None:
    packed = OfferAlertCallback(action=action).pack()  # type: ignore[arg-type]
    assert OfferAlertCallback.unpack(packed).action == action
