"""Тесты инлайн-обработчиков настроек рейтингов."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Message
from features.ratings import handlers
from features.ratings.enums import RatingAgency
from features.ratings.handlers import handle_toggle_agency
from features.ratings.schemas import RatingAlertCallback


def _callback() -> MagicMock:
    callback = MagicMock()
    callback.from_user.id = 555
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    return callback


async def test_toggle_updates_keyboard_and_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        handlers.RatingAlertSettingsRepository, "toggle", AsyncMock(return_value=True)
    )
    monkeypatch.setattr(
        handlers.RatingAlertSettingsRepository,
        "get_enabled_agencies",
        AsyncMock(return_value={RatingAgency.NRA}),
    )
    callback = _callback()

    await handle_toggle_agency(callback, RatingAlertCallback(action="toggle", agency="nra"))

    callback.message.edit_text.assert_awaited_once()
    callback.answer.assert_awaited_once()
    assert "Включено 🔔" in callback.answer.await_args.args[0]


async def test_toggle_unknown_agency_answers_error() -> None:
    callback = _callback()

    await handle_toggle_agency(
        callback, RatingAlertCallback(action="toggle", agency="unknown")
    )

    callback.message.edit_text.assert_not_awaited()
    callback.answer.assert_awaited_once_with("Неизвестное агентство")
