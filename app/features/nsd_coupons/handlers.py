"""Хендлеры подписки на уведомления о невыплаченных купонах."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .menu import render
from .repository import NsdCouponAlertSettingsRepository
from .schemas import NsdCouponAlertCallback

logger = logging.getLogger(__name__)

router: Router = Router()


@router.message(Command("coupon_alerts"))
async def show_settings(message: Message) -> None:
    """Показывает экран настроек подписки на уведомления о купонах."""
    if message.from_user is None:
        return
    text, markup = await render(message.from_user.id)
    await message.answer(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(NsdCouponAlertCallback.filter(F.action == "toggle"))
async def handle_toggle(callback: CallbackQuery) -> None:
    """Переключает подписку на уведомления о купонах и обновляет экран секции."""
    telegram_id = callback.from_user.id
    try:
        new_state = await NsdCouponAlertSettingsRepository.toggle(telegram_id)
        text, markup = await render(telegram_id)
        if isinstance(callback.message, Message):
            await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        await callback.answer(
            "Контроль купонов: " + ("включён" if new_state else "выключен")
        )
    except Exception as e:
        logger.error("Ошибка переключения подписки на купоны %s: %s", telegram_id, e)
        await callback.answer("Произошла ошибка")
