"""Инлайн-обработчики настроек уведомлений о раскрытиях эмитентов."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from features.analytics import EventName, track

from .enums import RISK_CHOICE_TITLES
from .menu import render
from .repository import DisclosureAlertSettingsRepository
from .schemas import RISK_LEVELS, DisclosureAlertCallback

logger = logging.getLogger(__name__)

router: Router = Router()


async def _refresh(callback: CallbackQuery, telegram_id: int) -> None:
    """Перерисовывает экран секции после изменения настроек."""
    text, markup = await render(telegram_id)
    if callback.message and isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(DisclosureAlertCallback.filter(F.action == "toggle"))
async def handle_toggle(callback: CallbackQuery) -> None:
    """Переключает подписку на раскрытия и обновляет клавиатуру."""
    telegram_id = callback.from_user.id

    try:
        new_state = await DisclosureAlertSettingsRepository.toggle(telegram_id)
        await track(
            EventName.ALERT_TOGGLED,
            telegram_id=telegram_id,
            action="disclosure",
            feature="disclosure",
            enabled=new_state,
        )

        await _refresh(callback, telegram_id)
        await callback.answer("Раскрытия: " + ("Включено 🔔" if new_state else "Выключено 🔕"))
    except Exception as e:
        logger.error(f"Ошибка при переключении раскрытий для {telegram_id}: {e}")
        await callback.answer("Произошла ошибка")


@router.callback_query(DisclosureAlertCallback.filter(F.action == "level"))
async def handle_level(
    callback: CallbackQuery, callback_data: DisclosureAlertCallback
) -> None:
    """Меняет минимальный уровень риска, при котором приходит уведомление."""
    telegram_id = callback.from_user.id
    level = callback_data.level

    # Шкалу задаёт воркер; неизвестное значение — только из подделанного callback.
    if level not in RISK_LEVELS:
        await callback.answer("Неизвестный уровень риска")
        return

    try:
        await DisclosureAlertSettingsRepository.set_min_risk_level(telegram_id, level)
        await track(
            EventName.ALERT_TOGGLED,
            telegram_id=telegram_id,
            action="disclosure_level",
            feature="disclosure",
            level=level,
        )

        await _refresh(callback, telegram_id)
        await callback.answer(RISK_CHOICE_TITLES[level])
    except Exception as e:
        logger.error(f"Ошибка при смене порога раскрытий для {telegram_id}: {e}")
        await callback.answer("Произошла ошибка")
