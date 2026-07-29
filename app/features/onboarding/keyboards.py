"""Клавиатуры онбординг-воронки."""

from __future__ import annotations

from aiogram.utils.keyboard import InlineKeyboardBuilder

from .schemas import MARKET_CALLBACK, TOKEN_CALLBACK, OnboardingNav
from .texts import OnboardingStep


def build_step_keyboard(step: OnboardingStep) -> InlineKeyboardBuilder:
    """Собирает инлайн-клавиатуру для экрана воронки.

    Args:
        step: Шаг воронки, для которого строятся кнопки.

    Returns:
        Билдер с кнопкой «Далее →» и/или кнопками выбора режима работы.

    """
    builder = InlineKeyboardBuilder()
    if step.next_index is not None:
        builder.button(text="Далее →", callback_data=OnboardingNav(step=step.next_index))
    if step.cta_token_label:
        builder.button(text=step.cta_token_label, callback_data=TOKEN_CALLBACK)
    if step.cta_market_label:
        builder.button(text=step.cta_market_label, callback_data=MARKET_CALLBACK)
    builder.adjust(1)
    return builder
