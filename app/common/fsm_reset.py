"""Сброс FSM при выходе из пошагового ввода через главное меню.

Пошаговый ввод (токен, пороги цен, время напоминания, рассылка) живёт в FSM.
Уйти с такого экрана можно было кнопкой главной клавиатуры или ``/start``:
``base.router`` подключён первым, и его хендлеры не несут ``StateFilter``,
поэтому апдейт доставался им, а не хендлеру состояния. Вот только состояние
при этом оставалось висеть — и следующее произвольное сообщение снова уходило
в ожидание токена или порога.

Мидлварь закрывает именно этот разрыв: если пользователь явно ушёл в главное
меню, ожидание ввода закончилось.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, TelegramObject
from core.enums import MainKeyboardButtonTexts

logger = logging.getLogger(__name__)

_MENU_TEXTS = frozenset(item.value for item in MainKeyboardButtonTexts)

# Команды, которые начинают флоу заново и потому несовместимы с ожиданием ввода.
# `/cancel` сбрасывает состояние сам и в списке не нужен.
_RESET_COMMANDS = frozenset({"start"})


def _is_exit(message: Message) -> bool:
    """Уводит ли сообщение пользователя из пошагового ввода."""
    text = message.text or ""
    if text in _MENU_TEXTS:
        return True
    if not text.startswith("/"):
        return False
    command = text[1:].partition(" ")[0].split("@", 1)[0]
    return command in _RESET_COMMANDS


class FsmResetMiddleware(BaseMiddleware):
    """Чистит FSM, когда пользователь уходит в главное меню или на ``/start``."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """Сбрасывает состояние до вызова хендлера, если это выход из ввода."""
        state = data.get("state")
        if isinstance(event, Message) and isinstance(state, FSMContext) and _is_exit(event):
            if await state.get_state() is not None:
                logger.info(f"Сброс FSM пользователя {event.chat.id}: выход в главное меню")
                await state.clear()
        return await handler(event, data)
