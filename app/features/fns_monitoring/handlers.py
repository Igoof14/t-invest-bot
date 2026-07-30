"""Инлайн-обработчики настроек уведомлений о блокировках ФНС."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from common.utils.bot_utils import safe_edit_text
from features.analytics import EventName, track

from .menu import render
from .repository import FnsAlertSettingsRepository
from .schemas import FnsAlertCallback

logger = logging.getLogger(__name__)

router: Router = Router()


@router.callback_query(FnsAlertCallback.filter(F.action == "toggle"))
async def handle_toggle(callback: CallbackQuery) -> None:
    """Переключает подписку на блокировки ФНС и обновляет клавиатуру."""
    telegram_id = callback.from_user.id

    try:
        new_state = await FnsAlertSettingsRepository.toggle(telegram_id)
        await track(
            EventName.ALERT_TOGGLED,
            telegram_id=telegram_id,
            action="fns",
            feature="fns",
            enabled=new_state,
        )

        text, markup = await render(telegram_id)
        if callback.message and isinstance(callback.message, Message):
            await safe_edit_text(callback.message, text, reply_markup=markup)

        await callback.answer("Блокировки ФНС: " + ("Включено 🔔" if new_state else "Выключено 🔕"))
    except Exception as e:
        logger.error(f"Ошибка при переключении блокировок ФНС для {telegram_id}: {e}")
        await callback.answer("Произошла ошибка")


@router.callback_query(FnsAlertCallback.filter(F.action == "scan"))
async def handle_scan(callback: CallbackQuery) -> None:
    """Отвечает на разовую проверку, пока сервис отключён.

    Кнопка из клавиатуры убрана (см. :mod:`.keyboards`), но callback остаётся
    живым в старых сообщениях — на него нужно ответить внятно, а не гонять
    пользователя через минуту ожидания к «Модулю в ремонте».
    """
    await callback.answer("Разовая проверка временно недоступна", show_alert=True)
