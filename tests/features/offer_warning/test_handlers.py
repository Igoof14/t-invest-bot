"""Тесты обработчиков и FSM уведомлений об офертах."""

from __future__ import annotations

from datetime import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Message
from core.clients.backend.notifications import OfferAlertSettings
from features.offer_warning import handlers
from features.offer_warning.handlers import (
    OfferAlertStates,
    handle_set_settings,
    process_first_alert,
    process_second_alert,
    process_time_alert,
)
from features.offer_warning.schemas import OfferAlertCallback


def _message(text: str, chat_id: int = 555) -> MagicMock:
    """Создаёт мок входящего сообщения."""
    msg = MagicMock()
    msg.text = text
    msg.chat.id = chat_id
    msg.answer = AsyncMock()
    msg.delete = AsyncMock()
    return msg


def _settings(**overrides: object) -> OfferAlertSettings:
    """Текущие настройки оферт с дефолтами 14/5/10:00."""
    base = {
        "alerts_enabled": True,
        "first_alert": 14,
        "second_alert": 5,
        "notification_time": time(10, 0),
    }
    return OfferAlertSettings(**{**base, **overrides})  # type: ignore[arg-type]


@pytest.fixture
def state() -> MagicMock:
    """Мок FSM-контекста."""
    fsm = MagicMock()
    fsm.set_state = AsyncMock()
    fsm.clear = AsyncMock()
    return fsm


@pytest.fixture
def repo(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Репозиторий настроек с успешной записью и дефолтным состоянием."""
    update = AsyncMock(return_value=True)
    get = AsyncMock(return_value=_settings())
    monkeypatch.setattr(handlers.OfferSettingsRepository, "update", update)
    monkeypatch.setattr(handlers.OfferSettingsRepository, "get", get)
    return MagicMock(update=update, get=get)


# --- process_first_alert -----------------------------------------------------


async def test_first_alert_rejects_non_digit(repo: MagicMock, state: MagicMock) -> None:
    msg = _message("abc")
    await process_first_alert(msg, state)
    msg.answer.assert_awaited_once()
    repo.update.assert_not_called()
    state.clear.assert_not_called()


@pytest.mark.parametrize("value", ["0", "51"])
async def test_first_alert_rejects_out_of_range(
    repo: MagicMock, state: MagicMock, value: str
) -> None:
    await process_first_alert(_message(value), state)
    repo.update.assert_not_called()


async def test_first_alert_saves_valid_value(repo: MagicMock, state: MagicMock) -> None:
    await process_first_alert(_message("20"), state)
    repo.update.assert_awaited_once_with(555, first_alert=20)
    state.clear.assert_awaited_once()


async def test_first_alert_must_be_earlier_than_second(
    repo: MagicMock, state: MagicMock
) -> None:
    """Первое напоминание не может быть позже второго (второе — 5 дней)."""
    msg = _message("3")
    await process_first_alert(msg, state)

    repo.update.assert_not_called()
    state.clear.assert_not_called()
    assert "раньше второго" in msg.answer.await_args.args[0]


# --- process_second_alert ----------------------------------------------------


async def test_second_alert_rejects_non_digit(repo: MagicMock, state: MagicMock) -> None:
    await process_second_alert(_message("x"), state)
    repo.update.assert_not_called()


async def test_second_alert_saves_valid_value(repo: MagicMock, state: MagicMock) -> None:
    await process_second_alert(_message("5"), state)
    repo.update.assert_awaited_once_with(555, second_alert=5)
    state.clear.assert_awaited_once()


async def test_second_alert_must_be_later_than_first(
    repo: MagicMock, state: MagicMock
) -> None:
    """Промпт обещает «меньше первого» — теперь это и проверяется."""
    msg = _message("30")
    await process_second_alert(msg, state)

    repo.update.assert_not_called()
    state.clear.assert_not_called()
    assert "позже первого" in msg.answer.await_args.args[0]


# --- process_time_alert ------------------------------------------------------


async def test_time_alert_rejects_bad_format(repo: MagicMock, state: MagicMock) -> None:
    await process_time_alert(_message("25:99"), state)
    repo.update.assert_not_called()
    state.clear.assert_not_called()


async def test_time_alert_saves_valid_time(repo: MagicMock, state: MagicMock) -> None:
    await process_time_alert(_message("09:30"), state)
    repo.update.assert_awaited_once_with(555, notification_time=time(9, 30))
    state.clear.assert_awaited_once()


# --- отказ бэкенда -----------------------------------------------------------


async def test_failed_save_reports_error_and_keeps_state(
    repo: MagicMock, state: MagicMock
) -> None:
    """Сообщать об успехе, когда запись не прошла, нельзя."""
    repo.update.return_value = False
    msg = _message("09:30")

    await process_time_alert(msg, state)

    assert "Не удалось сохранить" in msg.answer.await_args.args[0]
    # Состояние остаётся: значение можно отправить повторно.
    state.clear.assert_not_called()


# --- handle_set_settings -----------------------------------------------------


@pytest.mark.parametrize(
    ("action", "expected_state"),
    [
        ("set_first", OfferAlertStates.waiting_for_first),
        ("set_second", OfferAlertStates.waiting_for_second),
        ("set_time", OfferAlertStates.waiting_for_time),
    ],
)
async def test_handle_set_settings_sets_state_and_answers(
    state: MagicMock, action: str, expected_state: object
) -> None:
    """Квитируется нажатие всех трёх кнопок, а не только «Время уведомления»."""
    callback = MagicMock()
    callback.message = MagicMock(spec=Message)
    callback.message.answer = AsyncMock()
    callback.answer = AsyncMock()
    callback_data = OfferAlertCallback(action=action)  # type: ignore[arg-type]

    await handle_set_settings(callback, callback_data, state)

    state.set_state.assert_awaited_once_with(expected_state)
    callback.answer.assert_awaited_once()


# --- handle_toggle_alerts ----------------------------------------------------


async def test_handle_toggle_enabled_edits_message(
    monkeypatch: pytest.MonkeyPatch, repo: MagicMock
) -> None:
    monkeypatch.setattr(
        handlers.OfferSettingsRepository,
        "toggle_alerts",
        AsyncMock(return_value=True),
    )
    callback = MagicMock()
    callback.from_user.id = 555
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()

    await handlers.handle_toggle_alerts(callback, OfferAlertCallback(action="toggle"))

    callback.message.edit_text.assert_awaited_once()
    text = callback.message.edit_text.call_args.args[0]
    assert "включен" in text
    callback.answer.assert_awaited_once()


async def test_setting_screen_blocked_while_alerts_disabled(
    monkeypatch: pytest.MonkeyPatch, repo: MagicMock
) -> None:
    """Настраивать выключенные напоминания нечего — экран не открывается."""
    repo.get.return_value = _settings(alerts_enabled=False)
    callback = MagicMock()
    callback.from_user.id = 555
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()

    await handlers.handle_offer_alert_setting(callback)

    callback.message.edit_text.assert_not_called()
    callback.answer.assert_awaited_once_with("Сначала включите уведомления")
