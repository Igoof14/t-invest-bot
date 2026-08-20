"""Хендлеры онбординг-воронки.

Карусель из нескольких экранов, прогревающая нового пользователя перед
подключением токена. Навигация редактирует одно сообщение на месте.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from common.utils.bot_utils import safe_edit_text
from features.analytics import EventName, track

from .keyboards import build_step_keyboard
from .schemas import MARKET_CALLBACK, TOKEN_CALLBACK, OnboardingNav
from .texts import STEPS

logger = logging.getLogger(__name__)
router = Router()


async def start_onboarding(message: Message) -> None:
    """Показывает первый экран воронки.

    Вызывается из обработчика ``/start`` для пользователей без токена.

    Args:
        message: Сообщение пользователя, в чат которого отправить воронку.

    """
    step = STEPS[0]
    await message.answer(
        step.text,
        reply_markup=build_step_keyboard(step).as_markup(),
        parse_mode="HTML",
    )
    await track(EventName.ONBOARDING_STEP_SHOWN, telegram_id=message.chat.id, step=0)


@router.callback_query(OnboardingNav.filter())
async def handle_nav(callback: CallbackQuery, callback_data: OnboardingNav) -> None:
    """Переключает воронку на выбранный шаг, редактируя текущее сообщение."""
    if not 0 <= callback_data.step < len(STEPS):
        await callback.answer()
        return
    step = STEPS[callback_data.step]
    if isinstance(callback.message, Message):
        await safe_edit_text(
            callback.message,
            step.text,
            reply_markup=build_step_keyboard(step).as_markup(),
        )
    await track(
        EventName.ONBOARDING_STEP_SHOWN,
        telegram_id=callback.from_user.id,
        step=callback_data.step,
    )
    await callback.answer()


@router.callback_query(F.data == TOKEN_CALLBACK)
async def handle_token_cta(callback: CallbackQuery) -> None:
    """Финальный CTA: показывает кнопку открытия мини-аппа."""
    # Отложенный импорт: разрывает цикл base -> onboarding -> users -> base.
    from features.users.handlers import prompt_open_miniapp

    await track(EventName.ONBOARDING_CTA_CLICKED, telegram_id=callback.from_user.id)
    if isinstance(callback.message, Message):
        await prompt_open_miniapp(callback.message, entry="onboarding")
    await callback.answer()


@router.callback_query(F.data == MARKET_CALLBACK)
async def handle_market_cta(callback: CallbackQuery) -> None:
    """Второй вариант финального шага: работать без токена, по всему рынку.

    Ничего не включает — дефолтные настройки уведомлений бэкенд создал ещё на
    ``/start``. Кнопка только фиксирует выбор в аналитике и показывает, где
    эти настройки крутить.
    """
    # Отложенный импорт: разрывает цикл base -> onboarding -> menu -> base.
    from features.menu import render_hub

    telegram_id = callback.from_user.id
    await track(EventName.ONBOARDING_MARKET_CHOSEN, telegram_id=telegram_id)
    if isinstance(callback.message, Message):
        text, markup = await render_hub(telegram_id)
        await safe_edit_text(callback.message, text, reply_markup=markup)
    await callback.answer()
