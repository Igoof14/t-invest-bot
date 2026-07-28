"""Хендлеры админской рассылки `/broadcast`.

Доступ только у `config.admin_id`. Флоу: команда → присылаем сообщение →
превью с подтверждением → рассылка → отчёт.
"""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from core.config import config
from features.users.repository import BotUserRepository

from .keyboards import confirm_keyboard
from .schemas import BROADCAST_CANCEL, BROADCAST_CONFIRM
from .service import BroadcastService

logger = logging.getLogger(__name__)
router = Router()


class BroadcastStates(StatesGroup):
    """Состояния FSM рассылки."""

    waiting_for_message = State()
    waiting_for_confirmation = State()


def _is_admin(message: Message) -> bool:
    """Проверяет, что отправитель — администратор из конфига."""
    return (
        config.admin_id is not None
        and message.from_user is not None
        and message.from_user.id == config.admin_id
    )


@router.message(Command("broadcast"))
async def start_broadcast(message: Message, state: FSMContext) -> None:
    """Запускает рассылку: просит прислать сообщение (только админ)."""
    if not _is_admin(message):
        return
    await state.set_state(BroadcastStates.waiting_for_message)
    await message.answer(
        "Пришлите сообщение для рассылки (текст, фото — что угодно).\n"
        "Оно уйдёт пользователям как есть. Для отмены — /start."
    )


@router.message(BroadcastStates.waiting_for_message)
async def collect_message(message: Message, state: FSMContext) -> None:
    """Сохраняет сообщение и показывает превью с подтверждением."""
    await state.update_data(from_chat_id=message.chat.id, message_id=message.message_id)
    await state.set_state(BroadcastStates.waiting_for_confirmation)
    count = len(await BotUserRepository.get_all_active_users())
    await message.answer(
        f"Отправить это сообщение {count} активным пользователям?",
        reply_markup=confirm_keyboard().as_markup(),
    )


@router.callback_query(F.data == BROADCAST_CONFIRM, BroadcastStates.waiting_for_confirmation)
async def confirm_broadcast(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Выполняет рассылку и показывает отчёт."""
    data = await state.get_data()
    await state.clear()
    from_chat_id = data.get("from_chat_id")
    message_id = data.get("message_id")
    if from_chat_id is None or message_id is None:
        await callback.answer()
        return
    # Квитируем нажатие до рассылки, а не после: она идёт десятки секунд, а
    # callback query живёт считаные секунды. Ответ в конце падал с
    # "query is too old and response timeout expired or query ID is invalid",
    # хотя сама рассылка к тому моменту уже была доставлена.
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text("Отправляю…")
    result = await BroadcastService(bot).broadcast(from_chat_id, message_id)
    report = (
        f"Рассылка завершена.\n\n"
        f"Доставлено: {result.delivered}\n"
        f"Заблокировали: {result.blocked}\n"
        f"Ошибок: {result.failed}"
    )
    if isinstance(callback.message, Message):
        await callback.message.answer(report)


@router.callback_query(F.data == BROADCAST_CANCEL)
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext) -> None:
    """Отменяет рассылку."""
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.edit_text("Рассылка отменена.")
    await callback.answer()
