"""Callback-данные онбординг-воронки."""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData

# Финальный CTA — переход к вводу токена (без параметров).
TOKEN_CALLBACK = "onb:token"

# Второй вариант финального шага — работать без токена, по всему рынку.
MARKET_CALLBACK = "onb:market"


class OnboardingNav(CallbackData, prefix="onbnav"):
    """Навигация по шагам воронки.

    Attributes:
        step: Индекс шага в ``STEPS``, который нужно показать.

    """

    step: int
