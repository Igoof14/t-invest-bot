"""Роутер навигации по меню (открытие хаба и секций)."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from .callbacks import MenuCallback
from .keyboards import HUB_KEY, build_help, build_hub
from .registry import get_section, get_sections

logger = logging.getLogger(__name__)

router: Router = Router()


async def render_hub(telegram_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Возвращает экран хаба «Уведомления»."""
    return await build_hub(telegram_id, get_sections())


async def _edit(callback: CallbackQuery, text: str, markup: InlineKeyboardMarkup) -> None:
    """Перерисовывает сообщение на месте."""
    if callback.message and isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(MenuCallback.filter(F.section == HUB_KEY))
async def open_hub(callback: CallbackQuery, callback_data: MenuCallback) -> None:
    """Открывает корневой хаб."""
    try:
        text, markup = await render_hub(callback.from_user.id)
        await _edit(callback, text, markup)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при открытии хаба меню: {e}")
        await callback.answer("Произошла ошибка")


@router.callback_query(MenuCallback.filter((F.section != HUB_KEY) & (F.action == "help")))
async def open_section_help(callback: CallbackQuery, callback_data: MenuCallback) -> None:
    """Открывает описание секции «как это работает»."""
    section = get_section(callback_data.section)
    if section is None or section.help_text is None:
        await callback.answer("Описание недоступно")
        return
    try:
        text, markup = build_help(section)
        await _edit(callback, text, markup)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при открытии описания секции {callback_data.section}: {e}")
        await callback.answer("Произошла ошибка")


@router.callback_query(MenuCallback.filter((F.section != HUB_KEY) & (F.action == "open")))
async def open_section(callback: CallbackQuery, callback_data: MenuCallback) -> None:
    """Открывает экран секции через её ``render``."""
    section = get_section(callback_data.section)
    if section is None:
        await callback.answer("Раздел недоступен")
        return
    try:
        text, markup = await section.render(callback.from_user.id)
        await _edit(callback, text, markup)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при открытии секции {callback_data.section}: {e}")
        await callback.answer("Произошла ошибка")
