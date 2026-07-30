"""Секция меню «Раскрытия эмитентов»."""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from core.clients.backend.notifications import DisclosureAlertSettings, NotificationSettings
from features.menu import STALE_NOTE, MenuSection, back_to_hub_button, help_button, status_text

from .enums import (
    DISCLOSURE_ALERTS_DESCRIPTION,
    DISCLOSURE_ALERTS_HELP,
    RISK_CHOICE_TITLES,
    RISK_ICONS,
    RISK_TITLES,
)
from .keyboards import create_disclosure_alerts_keyboard
from .repository import DisclosureAlertSettingsRepository
from .schemas import RISK_LEVELS

SECTION_KEY = "disclosure"


def build_text(settings: DisclosureAlertSettings) -> str:
    """Собирает HTML-описание раздела с текущим статусом и порогом.

    Порог — это «этот уровень и выше», поэтому одной подписи мало: раздел
    перечисляет уровни, которые реально дойдут до пользователя.
    """
    status = "включено" if settings.alerts_enabled else "выключено"
    text = f"{DISCLOSURE_ALERTS_DESCRIPTION}\n\nСтатус: <b>{status}</b>"
    if not settings.alerts_enabled:
        return text + (STALE_NOTE if settings.stale else "")

    level = settings.min_risk_level
    # Шкала принадлежит воркеру и расширяется без миграций, поэтому незнакомый
    # уровень показываем как есть, а не роняем экран на KeyError.
    if level not in RISK_LEVELS:
        return f"{text}\n\nТекущий порог: <b>{level}</b>"

    passing = ", ".join(
        f"{RISK_ICONS[passed]} {RISK_TITLES[passed]}"
        for passed in RISK_LEVELS[RISK_LEVELS.index(level) :]
    )
    return (
        f"{text}\n\n"
        f"<b>Текущий порог:</b> {RISK_ICONS[level]} {RISK_CHOICE_TITLES[level]}\n\n"
        f"Приходят раскрытия: {passing}"
    )


async def render(telegram_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Экран настроек: тумблер + порог риска + «Как это работает» + «Назад»."""
    settings = await DisclosureAlertSettingsRepository.get(telegram_id)
    builder = create_disclosure_alerts_keyboard(settings.alerts_enabled, settings.min_risk_level)
    builder.row(help_button(SECTION_KEY))
    builder.row(back_to_hub_button())
    return build_text(settings), builder.as_markup()


def status_badge(settings: NotificationSettings) -> str:
    """Бейдж для хаба: включено, если пользователь подписан."""
    return status_text(settings.disclosure.alerts_enabled)


SECTION = MenuSection(
    key=SECTION_KEY,
    title="Раскрытия эмитентов",
    render=render,
    status_badge=status_badge,
    help_text=DISCLOSURE_ALERTS_HELP,
)
