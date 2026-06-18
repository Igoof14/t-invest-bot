"""Хендлеры онбординг-воронки.

Карусель из нескольких экранов, прогревающая нового пользователя перед
подключением токена. Навигация редактирует одно сообщение на месте.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from features.users.users_handlers import prompt_for_token

from .keyboards import build_step_keyboard
from .schemas import TOKEN_CALLBACK, OnboardingNav
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
        parse_mode="Markdown",
    )


@router.callback_query(OnboardingNav.filter())
async def handle_nav(callback: CallbackQuery, callback_data: OnboardingNav) -> None:
    """Переключает воронку на выбранный шаг, редактируя текущее сообщение."""
    if not 0 <= callback_data.step < len(STEPS):
        await callback.answer()
        return
    step = STEPS[callback_data.step]
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            step.text,
            reply_markup=build_step_keyboard(step).as_markup(),
            parse_mode="Markdown",
        )
    await callback.answer()


@router.callback_query(F.data == TOKEN_CALLBACK)
async def handle_token_cta(callback: CallbackQuery, state: FSMContext) -> None:
    """Финальный CTA: открывает ввод токена."""
    if isinstance(callback.message, Message):
        await prompt_for_token(callback.message, state)
    await callback.answer()
