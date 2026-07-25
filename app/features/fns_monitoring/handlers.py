"""Инлайн-обработчики настроек уведомлений о блокировках ФНС."""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message

from .formatter import format_scan_report
from .menu import render
from .repository import FnsAlertSettingsRepository
from .schemas import FnsAlertCallback

logger = logging.getLogger(__name__)

router: Router = Router()

# Пользователи, чья разовая проверка сейчас выполняется (защита от двойного запуска).
_scanning: set[int] = set()


@router.callback_query(FnsAlertCallback.filter(F.action == "toggle"))
async def handle_toggle(callback: CallbackQuery) -> None:
    """Переключает подписку на блокировки ФНС и обновляет клавиатуру."""
    telegram_id = callback.from_user.id

    try:
        new_state = await FnsAlertSettingsRepository.toggle(telegram_id)

        text, markup = await render(telegram_id)
        if callback.message and isinstance(callback.message, Message):
            await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")

        await callback.answer(
            "Блокировки ФНС: " + ("Включено 🔔" if new_state else "Выключено 🔕")
        )
    except Exception as e:
        logger.error(f"Ошибка при переключении блокировок ФНС для {telegram_id}: {e}")
        await callback.answer("Произошла ошибка")


@router.callback_query(FnsAlertCallback.filter(F.action == "scan"))
async def handle_scan(callback: CallbackQuery, bot: Bot) -> None:
    """Разово проверяет эмитентов пользователя и показывает результат."""
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
            "🔄 Проверяю ваших эмитентов в ФНС…\nЭто может занять до нескольких минут.",
            parse_mode="HTML",
        )

        # report = await FnsBlockingMonitorService(bot).scan_user(telegram_id)
        # text = format_scan_report(report)
        text = "Модуль в ремонте"
        _, markup = await render(telegram_id)
        await message.edit_text(
            text,
            reply_markup=markup,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.error(f"Ошибка при проверке эмитентов для {telegram_id}: {e}")
        _, markup = await render(telegram_id)
        await message.edit_text(
            "Произошла ошибка при проверке. Попробуйте позже.",
            reply_markup=markup,
            parse_mode="HTML",
        )
    finally:
        _scanning.discard(telegram_id)
