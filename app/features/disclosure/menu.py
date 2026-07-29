"""Секция меню «Раскрытия эмитентов»."""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from features.menu import MenuSection, back_to_hub_button, help_button, status_text

from .enums import DISCLOSURE_ALERTS_DESCRIPTION, DISCLOSURE_ALERTS_HELP
from .keyboards import create_disclosure_alerts_keyboard
from .repository import DisclosureAlertSettingsRepository

SECTION_KEY = "disclosure"


async def render(telegram_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Экран настроек: тумблер + порог риска + «Как это работает» + «Назад»."""
    settings = await DisclosureAlertSettingsRepository.get(telegram_id)
    builder = create_disclosure_alerts_keyboard(
        settings.alerts_enabled, settings.min_risk_level
    )
    builder.row(help_button(SECTION_KEY))
    builder.row(back_to_hub_button())
    return DISCLOSURE_ALERTS_DESCRIPTION, builder.as_markup()


async def status_badge(telegram_id: int) -> str:
    """Бейдж для хаба: включено, если пользователь подписан."""
    settings = await DisclosureAlertSettingsRepository.get(telegram_id)
    return status_text(settings.alerts_enabled)


SECTION = MenuSection(
    key=SECTION_KEY,
    title="Раскрытия эмитентов",
    render=render,
    status_badge=status_badge,
    help_text=DISCLOSURE_ALERTS_HELP,
)
