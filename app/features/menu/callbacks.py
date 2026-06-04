"""Callback-данные навигации по меню."""

from aiogram.filters.callback_data import CallbackData


class MenuCallback(CallbackData, prefix="menu"):
    """Навигация по дереву меню.

    ``section`` — ключ секции (``"hub"`` для корневого хаба «Уведомления»).
    ``action`` — что показать: ``"open"`` (экран секции) или ``"help"``
    (описание «как это работает»).
    """

    section: str
    action: str = "open"
