"""Инлайн-обработчики настроек уведомлений о рейтингах."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from common.utils.bot_utils import safe_edit_text
from features.analytics import EventName, track

from .enums import RatingAgency
from .menu import render
from .repository import RatingAlertSettingsRepository
from .schemas import RatingAlertCallback

logger = logging.getLogger(__name__)

router: Router = Router()


@router.callback_query(RatingAlertCallback.filter(F.action == "toggle"))
async def handle_toggle_agency(callback: CallbackQuery, callback_data: RatingAlertCallback) -> None:
    """Переключает подписку на агентство и обновляет клавиатуру."""
    telegram_id = callback.from_user.id

    try:
        agency = RatingAgency(callback_data.agency)
    except ValueError:
        await callback.answer("Неизвестное агентство")
        return

    try:
        new_state = await RatingAlertSettingsRepository.toggle(telegram_id, agency)
        await track(
            EventName.ALERT_TOGGLED,
            telegram_id=telegram_id,
            action=f"rating:{agency.value}",
            feature="rating",
            agency=agency.value,
            enabled=new_state,
        )

        text, markup = await render(telegram_id)
        if callback.message and isinstance(callback.message, Message):
            await safe_edit_text(callback.message, text, reply_markup=markup)

        await callback.answer(
            f"{agency.display_name}: " + ("Включено 🔔" if new_state else "Выключено 🔕")
        )
    except Exception as e:
        logger.error(f"Ошибка при переключении рейтинга {agency.value} для {telegram_id}: {e}")
        await callback.answer("Произошла ошибка")
