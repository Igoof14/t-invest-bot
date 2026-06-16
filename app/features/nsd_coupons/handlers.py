"""Хендлеры подписки на уведомления о невыплаченных купонах."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .keyboards import create_coupon_alerts_keyboard
from .repository import NsdCouponAlertSettingsRepository
from .schemas import NsdCouponAlertCallback

logger = logging.getLogger(__name__)

router: Router = Router()

_SCREEN_TEXT = (
    "<b>📉 Контроль выплаты купонов</b>\n\n"
    "Бот сверяет купонный календарь ваших облигаций с публикациями НРД и "
    "сообщит, если по бумаге в портфеле купон не поступил в НРД к плановой дате "
    "(задержка или технический дефолт эмитента)."
)


@router.message(Command("coupon_alerts"))
async def show_settings(message: Message) -> None:
    """Показывает экран настроек подписки на уведомления о купонах."""
    if message.from_user is None:
        return
    enabled = await NsdCouponAlertSettingsRepository.is_enabled(message.from_user.id)
    await message.answer(
        _SCREEN_TEXT,
        reply_markup=create_coupon_alerts_keyboard(enabled),
        parse_mode="HTML",
    )


@router.callback_query(NsdCouponAlertCallback.filter(F.action == "toggle"))
async def handle_toggle(callback: CallbackQuery) -> None:
    """Переключает подписку на уведомления о купонах и обновляет клавиатуру."""
    telegram_id = callback.from_user.id
    try:
        new_state = await NsdCouponAlertSettingsRepository.toggle(telegram_id)
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                _SCREEN_TEXT,
                reply_markup=create_coupon_alerts_keyboard(new_state),
                parse_mode="HTML",
            )
        await callback.answer(
            "Контроль купонов: " + ("включён" if new_state else "выключен")
        )
    except Exception as e:
        logger.error("Ошибка переключения подписки на купоны %s: %s", telegram_id, e)
        await callback.answer("Произошла ошибка")
