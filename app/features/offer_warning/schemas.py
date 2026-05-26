from typing import Literal

from aiogram.filters.callback_data import CallbackData


class OfferAlertCallback(CallbackData, prefix="offer"):
    """Callback data для инлайн-кнопок уведомлений об офертах."""

    action: Literal["toggle", "setting", "set_first", "set_second", "set_time"]
