"""Тесты ввода порогов мониторинга цен."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from core.clients.backend.notifications import PriceAlertSettings
from features.price_monitoring import handlers
from features.price_monitoring.handlers import ThresholdStates, handle_threshold_input


def _message(text: str, chat_id: int = 111) -> MagicMock:
    msg = MagicMock()
    msg.text = text
    msg.chat.id = chat_id
    msg.answer = AsyncMock()
    msg.delete = AsyncMock()
    msg.bot = None
    return msg


def _state(current: str) -> MagicMock:
    state = MagicMock()
    state.get_state = AsyncMock(return_value=current)
    state.get_data = AsyncMock(return_value={})
    state.clear = AsyncMock()
    return state


@pytest.fixture
def repo(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Репозиторий с порогами 2/5 (падение) и 3/7 (рост)."""
    update = AsyncMock(return_value=True)
    get = AsyncMock(
        return_value=PriceAlertSettings(
            alerts_enabled=True,
            drop_warning_threshold=2.0,
            drop_critical_threshold=5.0,
            rise_warning_threshold=3.0,
            rise_critical_threshold=7.0,
        )
    )
    monkeypatch.setattr(handlers.AlertSettingsRepository, "update", update)
    monkeypatch.setattr(handlers.AlertSettingsRepository, "get", get)
    return MagicMock(update=update, get=get)


async def test_valid_threshold_is_saved(repo: MagicMock) -> None:
    state = _state(ThresholdStates.waiting_for_drop_warning.state)

    await handle_threshold_input(_message("3"), state)

    repo.update.assert_awaited_once_with(111, drop_warning_threshold=3.0)
    state.clear.assert_awaited_once()


async def test_warning_above_critical_is_rejected(repo: MagicMock) -> None:
    """«Умеренное 9% / Сильное 5%» — пара, при которой сильное не сработает."""
    state = _state(ThresholdStates.waiting_for_drop_warning.state)
    msg = _message("9")

    await handle_threshold_input(msg, state)

    repo.update.assert_not_called()
    state.clear.assert_not_called()
    assert "ниже" in msg.answer.await_args.args[0]


async def test_critical_below_warning_is_rejected(repo: MagicMock) -> None:
    state = _state(ThresholdStates.waiting_for_rise_critical.state)
    msg = _message("2")

    await handle_threshold_input(msg, state)

    repo.update.assert_not_called()
    assert "выше" in msg.answer.await_args.args[0]


async def test_failed_save_reports_error_and_keeps_state(repo: MagicMock) -> None:
    """Показывать «Порог успешно изменён», когда запись не прошла, нельзя."""
    repo.update.return_value = False
    state = _state(ThresholdStates.waiting_for_drop_warning.state)
    msg = _message("3")

    await handle_threshold_input(msg, state)

    assert "Не удалось сохранить" in msg.answer.await_args.args[0]
    state.clear.assert_not_called()


@pytest.mark.parametrize("text", ["abc", "0", "101"])
async def test_invalid_input_is_rejected(repo: MagicMock, text: str) -> None:
    state = _state(ThresholdStates.waiting_for_drop_warning.state)

    await handle_threshold_input(_message(text), state)

    repo.update.assert_not_called()
