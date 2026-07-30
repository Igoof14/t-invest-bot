"""Секция меню «Кредитные рейтинги»."""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from features.menu import STALE_NOTE, MenuSection, back_to_hub_button, help_button, status_text

from .enums import RATING_ALERTS_DESCRIPTION, RATING_ALERTS_HELP
from .keyboards import create_rating_alerts_keyboard
from .repository import RatingAlertSettingsRepository, RatingSubscriptions

SECTION_KEY = "ratings"


def build_text(subscriptions: RatingSubscriptions) -> str:
    """Описание раздела со статусом — как в остальных секциях хаба."""
    status = "включено" if subscriptions.agencies else "выключено"
    text = f"{RATING_ALERTS_DESCRIPTION}\n\nСтатус: <b>{status}</b>"
    if subscriptions.stale:
        text += STALE_NOTE
    return text


async def render(telegram_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Экран настроек рейтингов: тумблеры агентств + «Как это работает» + «Назад»."""
    subscriptions = await RatingAlertSettingsRepository.get(telegram_id)
    builder = create_rating_alerts_keyboard(set(subscriptions.agencies))
    builder.row(help_button(SECTION_KEY))
    builder.row(back_to_hub_button())
    return build_text(subscriptions), builder.as_markup()


async def status_badge(telegram_id: int) -> str:
    """Бейдж для хаба: включено, если подписано хотя бы одно агентство."""
    enabled = await RatingAlertSettingsRepository.get_enabled_agencies(telegram_id)
    return status_text(bool(enabled))


SECTION = MenuSection(
    key=SECTION_KEY,
    title="Кредитные рейтинги",
    render=render,
    status_badge=status_badge,
    help_text=RATING_ALERTS_HELP,
)
