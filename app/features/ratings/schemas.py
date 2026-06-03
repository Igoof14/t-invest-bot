"""Callback-данные для инлайн-кнопок настроек рейтингов."""

from typing import Literal

from aiogram.filters.callback_data import CallbackData


class RatingAlertCallback(CallbackData, prefix="rating"):
    """Callback data для тумблеров подписки на рейтинговые агентства."""

    action: Literal["toggle"]
    # Значение RatingAgency (например, "nra").
    agency: str
