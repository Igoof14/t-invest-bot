"""Хендлеры подписки на уведомления о невыплаченных купонах."""

from __future__ import annotations

import logging
import re
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
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

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_OFF_WORDS = {"выкл", "off", "выключить", "0", "-"}


class NsdReportStates(StatesGroup):
    """Состояния настройки ежедневного отчёта по купонам."""

    waiting_for_report_time = State()


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
        await callback.answer("Контроль купонов: " + ("включён" if new_state else "выключен"))
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


@router.callback_query(NsdCouponAlertCallback.filter(F.action == "set_report_time"))
async def handle_set_report_time(callback: CallbackQuery, state: FSMContext) -> None:
    """Запрашивает у пользователя время ежедневного отчёта."""
    if not isinstance(callback.message, Message):
        await callback.answer()
        return
    await callback.message.answer(
        "🕘 Введите время ежедневного отчёта по купонам в формате ЧЧ:ММ "
        "(например, 21:00), по МСК.\nЧтобы отключить отчёт — отправьте «выкл»."
    )
    await state.set_state(NsdReportStates.waiting_for_report_time)
    await callback.answer()


@router.message(NsdReportStates.waiting_for_report_time)
async def process_report_time(message: Message, state: FSMContext) -> None:
    """Сохраняет время ежедневного отчёта или выключает его."""
    text = (message.text or "").strip().lower()
    telegram_id = message.chat.id

    if text in _OFF_WORDS:
        await NsdCouponAlertSettingsRepository.set_report_time(telegram_id, None)
        await message.answer("Ежедневный отчёт по купонам выключен.")
        await state.clear()
        return

    if not _TIME_RE.match(text):
        await message.answer(
            "Неверный формат. Введите время как ЧЧ:ММ (например, 21:00) или «выкл»."
        )
        return

    report_time = datetime.strptime(text, "%H:%M").time()
    await NsdCouponAlertSettingsRepository.set_report_time(telegram_id, report_time)
    await message.answer(f"Готово: ежедневный отчёт по купонам в {text} МСК.")
    await state.clear()
