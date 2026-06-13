"""Callback-данные для инлайн-кнопок настроек блокировок ФНС."""

from typing import Literal

from aiogram.filters.callback_data import CallbackData


class FnsAlertCallback(CallbackData, prefix="fns"):
    """Callback data для кнопок раздела блокировок ФНС."""

    action: Literal["toggle", "scan"]
