"""Тесты обработчиков токена в features.users.handlers."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Message
from core.clients.backend.errors import BackendError, UserNotFound
from core.clients.t_invest.common_func import TokenCheck
from features.users import handlers as users_handlers
from features.users.handlers import (
    handle_rm_token,
    handle_rm_token_confirm,
    handle_token_message,
)


def _message(text: str, chat_id: int = 777) -> MagicMock:
    """Создаёт мок входящего сообщения."""
    msg = MagicMock()
    msg.text = text
    msg.chat.id = chat_id
    msg.answer = AsyncMock()
    msg.delete = AsyncMock()
    return msg


def _callback(telegram_id: int = 777) -> MagicMock:
    """Создаёт мок нажатия инлайн-кнопки."""
    callback = MagicMock()
    callback.from_user.id = telegram_id
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    return callback


@pytest.fixture
def state() -> MagicMock:
    """Мок FSM-контекста."""
    fsm = MagicMock()
    fsm.set_state = AsyncMock()
    fsm.clear = AsyncMock()
    return fsm


# --- приём токена ------------------------------------------------------------


async def test_valid_token_schedules_bonds_sync(
    monkeypatch: pytest.MonkeyPatch, state: MagicMock
) -> None:
    monkeypatch.setattr(
        users_handlers, "check_token", AsyncMock(return_value=TokenCheck.VALID)
    )
    monkeypatch.setattr(users_handlers.BotUserRepository, "add_token", AsyncMock(return_value=True))
    sync_user_bonds = AsyncMock(return_value=7)
    monkeypatch.setattr(users_handlers, "sync_user_bonds", sync_user_bonds)

    message = _message("t.valid")
    await handle_token_message(message, state)
    # Даём фоновой asyncio.Task шанс выполниться до проверки вызова.
    await asyncio.sleep(0)

    sync_user_bonds.assert_awaited_once_with(777)
    state.clear.assert_awaited_once()
    assert "Токен успешно сохранён" in message.answer.await_args_list[0].args[0]


async def test_token_message_is_deleted_from_chat(
    monkeypatch: pytest.MonkeyPatch, state: MagicMock
) -> None:
    """Токен в открытом виде не должен оставаться в истории чата."""
    monkeypatch.setattr(
        users_handlers, "check_token", AsyncMock(return_value=TokenCheck.VALID)
    )
    monkeypatch.setattr(users_handlers.BotUserRepository, "add_token", AsyncMock(return_value=True))
    monkeypatch.setattr(users_handlers, "sync_user_bonds", AsyncMock(return_value=0))

    message = _message("t.valid")
    await handle_token_message(message, state)
    await asyncio.sleep(0)

    message.delete.assert_awaited_once()


@pytest.mark.parametrize(
    ("bonds_synced", "expected"),
    [
        (7, "7 облигаций в портфеле"),
        (1, "1 облигация в портфеле"),
        (2, "2 облигации в портфеле"),
        (0, "облигаций в портфеле не нашлось"),
        (None, "Не удалось синхронизировать"),
    ],
)
async def test_sync_result_is_reported_to_user(
    monkeypatch: pytest.MonkeyPatch, state: MagicMock, bonds_synced: int | None, expected: str
) -> None:
    monkeypatch.setattr(
        users_handlers, "check_token", AsyncMock(return_value=TokenCheck.VALID)
    )
    monkeypatch.setattr(users_handlers.BotUserRepository, "add_token", AsyncMock(return_value=True))
    monkeypatch.setattr(users_handlers, "sync_user_bonds", AsyncMock(return_value=bonds_synced))

    message = _message("t.valid")
    await handle_token_message(message, state)
    await asyncio.sleep(0)

    assert expected in message.answer.await_args_list[-1].args[0]


async def test_invalid_token_does_not_schedule_sync(
    monkeypatch: pytest.MonkeyPatch, state: MagicMock
) -> None:
    monkeypatch.setattr(
        users_handlers, "check_token", AsyncMock(return_value=TokenCheck.INVALID)
    )
    add_token = AsyncMock()
    monkeypatch.setattr(users_handlers.BotUserRepository, "add_token", add_token)
    sync_user_bonds = AsyncMock()
    monkeypatch.setattr(users_handlers, "sync_user_bonds", sync_user_bonds)

    message = _message("t.invalid")
    await handle_token_message(message, state)

    add_token.assert_not_called()
    sync_user_bonds.assert_not_called()
    assert "Некорректный токен" in message.answer.await_args.args[0]
    # Состояние держим: пользователь может отправить токен ещё раз.
    state.clear.assert_not_called()


async def test_unreachable_t_invest_is_not_reported_as_bad_token(
    monkeypatch: pytest.MonkeyPatch, state: MagicMock
) -> None:
    """Сбой связи с T-Invest — не «некорректный токен»."""
    monkeypatch.setattr(
        users_handlers, "check_token", AsyncMock(return_value=TokenCheck.UNAVAILABLE)
    )
    add_token = AsyncMock()
    monkeypatch.setattr(users_handlers.BotUserRepository, "add_token", add_token)

    message = _message("t.valid")
    await handle_token_message(message, state)

    add_token.assert_not_called()
    text = message.answer.await_args.args[0]
    assert "Не удалось проверить токен" in text
    assert "Некорректный" not in text


async def test_save_failure_does_not_schedule_sync(
    monkeypatch: pytest.MonkeyPatch, state: MagicMock
) -> None:
    monkeypatch.setattr(
        users_handlers, "check_token", AsyncMock(return_value=TokenCheck.VALID)
    )
    monkeypatch.setattr(
        users_handlers.BotUserRepository, "add_token", AsyncMock(return_value=False)
    )
    sync_user_bonds = AsyncMock()
    monkeypatch.setattr(users_handlers, "sync_user_bonds", sync_user_bonds)

    await handle_token_message(_message("t.valid"), state)

    sync_user_bonds.assert_not_called()


# --- удаление токена ---------------------------------------------------------


async def test_delete_without_token_does_not_ask_for_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Удалять нечего — подтверждение не показывается, экран честно обновляется."""
    monkeypatch.setattr(users_handlers, "has_token", AsyncMock(return_value=False))
    remove_token = AsyncMock()
    monkeypatch.setattr(users_handlers.BotUserRepository, "remove_token", remove_token)
    callback = _callback()

    await handle_rm_token(callback)

    remove_token.assert_not_called()
    assert "не подключён" in callback.answer.await_args.args[0]
    assert "не подключён" in callback.message.edit_text.await_args.args[0]


async def test_delete_with_token_asks_for_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(users_handlers, "has_token", AsyncMock(return_value=True))
    callback = _callback()

    await handle_rm_token(callback)

    assert "Удалить токен?" in callback.message.edit_text.await_args.args[0]


async def test_delete_confirm_reports_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        users_handlers.BotUserRepository, "remove_token", AsyncMock(return_value=True)
    )
    monkeypatch.setattr(users_handlers, "has_token", AsyncMock(return_value=False))
    callback = _callback()

    await handle_rm_token_confirm(callback)

    assert "Токен удалён" in callback.answer.await_args.args[0]


async def test_delete_confirm_distinguishes_missing_token_from_backend_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Раньше оба случая давали одно «Ошибка при удалении токена»."""
    monkeypatch.setattr(users_handlers, "has_token", AsyncMock(return_value=False))

    monkeypatch.setattr(
        users_handlers.BotUserRepository,
        "remove_token",
        AsyncMock(side_effect=UserNotFound("нет такого пользователя")),
    )
    callback = _callback()
    await handle_rm_token_confirm(callback)
    assert "и так не был подключён" in callback.answer.await_args.args[0]

    monkeypatch.setattr(
        users_handlers.BotUserRepository,
        "remove_token",
        AsyncMock(side_effect=BackendError("бэкенд лежит")),
    )
    callback = _callback()
    await handle_rm_token_confirm(callback)
    assert "Не удалось удалить токен" in callback.answer.await_args.args[0]
