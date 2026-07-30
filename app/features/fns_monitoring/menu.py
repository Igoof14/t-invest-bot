"""Секция меню «Блокировки счетов ФНС»."""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from core.clients.backend.notifications import FnsAlertSettings
from features.menu import STALE_NOTE, MenuSection, back_to_hub_button, help_button, status_text

from .enums import FNS_ALERTS_DESCRIPTION, FNS_ALERTS_HELP
from .keyboards import create_fns_alerts_keyboard
from .repository import FnsAlertSettingsRepository

SECTION_KEY = "fns_blocking"


def build_text(settings: FnsAlertSettings) -> str:
    """Описание раздела со статусом — как в остальных секциях хаба."""
    status = "включено" if settings.alerts_enabled else "выключено"
    text = f"{FNS_ALERTS_DESCRIPTION}\n\nСтатус: <b>{status}</b>"
    if settings.stale:
        text += STALE_NOTE
    return text


async def render(telegram_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Экран настроек: тумблер блокировок + «Как это работает» + «Назад»."""
    settings = await FnsAlertSettingsRepository.get(telegram_id)
    builder = create_fns_alerts_keyboard(settings.alerts_enabled)
    builder.row(help_button(SECTION_KEY))
    builder.row(back_to_hub_button())
    return build_text(settings), builder.as_markup()


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
