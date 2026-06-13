"""Секция меню «Блокировки счетов ФНС»."""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from features.menu import MenuSection, back_to_hub_button, help_button, status_text

from .enums import FNS_ALERTS_DESCRIPTION, FNS_ALERTS_HELP
from .keyboards import create_fns_alerts_keyboard
from .repository import FnsAlertSettingsRepository

SECTION_KEY = "fns_blocking"


async def render(telegram_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Экран настроек: тумблер блокировок + «Как это работает» + «Назад»."""
    enabled = await FnsAlertSettingsRepository.is_enabled(telegram_id)
    builder = create_fns_alerts_keyboard(enabled)
    builder.row(help_button(SECTION_KEY))
    builder.row(back_to_hub_button())
    return FNS_ALERTS_DESCRIPTION, builder.as_markup()


async def status_badge(telegram_id: int) -> str:
    """Бейдж для хаба: включено, если пользователь подписан."""
    enabled = await FnsAlertSettingsRepository.is_enabled(telegram_id)
    return status_text(enabled)


SECTION = MenuSection(
    key=SECTION_KEY,
    title="Блокировки счетов ФНС",
    render=render,
    status_badge=status_badge,
    help_text=FNS_ALERTS_HELP,
)
