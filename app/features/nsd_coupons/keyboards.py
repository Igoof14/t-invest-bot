"""Клавиатура настроек уведомлений о невыплаченных купонах."""

from __future__ import annotations

from datetime import time

from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .schemas import NsdCouponAlertCallback


def create_coupon_alerts_keyboard(
    enabled: bool, report_time: time | None = None
) -> InlineKeyboardBuilder:
    """Создаёт билдер с тумблером подписки, проверкой и временем отчёта.

    Возвращает билдер (а не готовую разметку), чтобы секция меню могла добавить
    к нему кнопки «как это работает» и «назад».

    Args:
        enabled: Включены ли уведомления у пользователя.
        report_time: Время ежедневного отчёта по МСК (``None`` — отчёт выключен).

    Returns:
        Билдер с кнопками тумблера, проверки и настройки времени отчёта.
    """
    builder = InlineKeyboardBuilder()
    mark = "Включено 🔔" if enabled else "Выключено 🔕"
    builder.row(
        InlineKeyboardButton(
            text=f"Купоны не пришли: {mark}",
            callback_data=NsdCouponAlertCallback(action="toggle").pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔍 Проверить мои купоны",
            callback_data=NsdCouponAlertCallback(action="scan").pack(),
        )
    )
    report_mark = report_time.strftime("%H:%M") if report_time else "выкл"
    builder.row(
        InlineKeyboardButton(
            text=f"🕘 Ежедневный отчёт: {report_mark}",
            callback_data=NsdCouponAlertCallback(action="set_report_time").pack(),
        )
    )
    return builder
