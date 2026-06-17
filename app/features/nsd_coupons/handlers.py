"""Хендлеры подписки на уведомления о невыплаченных купонах."""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .formatter import format_scan_report
from .menu import render
from .repository import NsdCouponAlertSettingsRepository
from .schemas import NsdCouponAlertCallback
from .service import NsdCouponService

logger = logging.getLogger(__name__)

router: Router = Router()

# Пользователи, чья разовая проверка сейчас выполняется (защита от двойного запуска).
_scanning: set[int] = set()


@router.message(Command("coupon_alerts"))
async def show_settings(message: Message) -> None:
    """Показывает экран настроек подписки на уведомления о купонах."""
    if message.from_user is None:
        return
    text, markup = await render(message.from_user.id)
    await message.answer(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(NsdCouponAlertCallback.filter(F.action == "toggle"))
async def handle_toggle(callback: CallbackQuery) -> None:
    """Переключает подписку на уведомления о купонах и обновляет экран секции."""
    telegram_id = callback.from_user.id
    try:
        new_state = await NsdCouponAlertSettingsRepository.toggle(telegram_id)
        text, markup = await render(telegram_id)
        if isinstance(callback.message, Message):
            await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        await callback.answer(
            "Контроль купонов: " + ("включён" if new_state else "выключен")
        )
    except Exception as e:
        logger.error("Ошибка переключения подписки на купоны %s: %s", telegram_id, e)
        await callback.answer("Произошла ошибка")


@router.callback_query(NsdCouponAlertCallback.filter(F.action == "scan"))
async def handle_scan(callback: CallbackQuery, bot: Bot) -> None:
    """Разово проверяет купоны пользователя за вчера/сегодня и показывает сводку."""
    telegram_id = callback.from_user.id
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer()
        return

    if telegram_id in _scanning:
        await callback.answer("Проверка уже идёт, подождите…")
        return

    await callback.answer()
    _scanning.add(telegram_id)
    try:
        await message.edit_text(
            "🔄 Проверяю ваши купоны за вчера и сегодня по данным НРД…\n"
            "Это может занять до минуты.",
            parse_mode="HTML",
        )
        report = await NsdCouponService(bot).scan_user(telegram_id)
        text = format_scan_report(report)
        _, markup = await render(telegram_id)
        await message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception as e:
        logger.error("Ошибка проверки купонов для %s: %s", telegram_id, e)
        _, markup = await render(telegram_id)
        await message.edit_text(
            "Произошла ошибка при проверке. Попробуйте позже.",
            reply_markup=markup,
            parse_mode="HTML",
        )
    finally:
        _scanning.discard(telegram_id)
