"""Клавиатуры онбординг-воронки."""

from __future__ import annotations

from aiogram.utils.keyboard import InlineKeyboardBuilder

from .schemas import TOKEN_CALLBACK, OnboardingNav
from .texts import QUICK_CONNECT_LABEL, OnboardingStep


def build_step_keyboard(step: OnboardingStep) -> InlineKeyboardBuilder:
    """Собирает инлайн-клавиатуру для экрана воронки.

    Args:
        step: Шаг воронки, для которого строятся кнопки.

    Returns:
        Билдер с кнопками «Далее →», финальным CTA и/или «Подключить сразу».

    """
    builder = InlineKeyboardBuilder()
    if step.next_index is not None:
        builder.button(text="Далее →", callback_data=OnboardingNav(step=step.next_index))
    if step.cta_token_label:
        builder.button(text=step.cta_token_label, callback_data=TOKEN_CALLBACK)
    if step.show_quick_connect:
        builder.button(text=QUICK_CONNECT_LABEL, callback_data=TOKEN_CALLBACK)
    builder.adjust(1)
    return builder
