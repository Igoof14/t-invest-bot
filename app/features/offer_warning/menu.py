"""Секция меню «Напоминание об оферте»."""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from common.utils.bot_utils import pluralize_days
from core.clients.backend.notifications import OfferAlertSettings
from features.menu import MenuSection, back_to_hub_button, help_button, status_text

from .keyboards import create_offer_alerts_keyboard
from .repository import OfferSettingsRepository

SECTION_KEY = "offer"

OFFER_ALERT_HELP = (
    "<b>Как это работает</b>\n\n"
    "• Выберите за сколько дней напомнить (например, за 20 и за 7 дней)\n"
    "• Укажите удобное время уведомления\n"
    "• Бот напомнит вам точно в срок\n\n"
    '<a href="https://www.google.com/search?q=что+такое+оферта+в+облигациях">'
    "Что такое оферта</a>"
)


def build_text(settings: OfferAlertSettings) -> str:
    """Собирает HTML-описание раздела с текущим статусом и настройками."""
    status = "включено" if settings.alerts_enabled else "выключено"
    text = (
        "<b>Напоминание об оферте</b>\n\n"
        "Не пропустите важную дату — получайте уведомления о приближающейся "
        "оферте (PUT-опцион) заранее.\n\n"
        f"Статус: <b>{status}</b>"
    )
    if settings.alerts_enabled:
        text += (
            "\n\n<b>Текущие настройки:</b>\n\n"
            f"Первое напоминание за: {settings.first_alert} "
            f"{pluralize_days(settings.first_alert)}\n"
            f"Второе напоминание за: {settings.second_alert} "
            f"{pluralize_days(settings.second_alert)}\n"
            f"Время уведомления: {str(settings.notification_time)[:-3]} МСК"
        )
    return text


async def render(telegram_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Экран раздела оферт: тумблер/настройки + «Как это работает» + «Назад»."""
    settings = await OfferSettingsRepository.get(telegram_id)
    builder = create_offer_alerts_keyboard(settings.alerts_enabled)
    builder.row(back_to_hub_button())
    builder.row(help_button(SECTION_KEY))

    if settings.alerts_enabled:
        builder.adjust(1, 1, 2)
    else:
        builder.adjust(1, 2)
    return build_text(settings), builder.as_markup()


async def status_badge(telegram_id: int) -> str:
    """Бейдж для хаба: включено, если уведомления активны."""
    settings = await OfferSettingsRepository.get(telegram_id)
    return status_text(settings.alerts_enabled)


SECTION = MenuSection(
    key=SECTION_KEY,
    title="Напоминание об оферте",
    render=render,
    status_badge=status_badge,
    help_text=OFFER_ALERT_HELP,
)
