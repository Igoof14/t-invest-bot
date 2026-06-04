"""Секция меню «Мониторинг цен»."""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from features.menu import MenuSection, back_to_hub_button, help_button, status_text

from .keyboards import create_price_alerts_keyboard
from .models import PriceAlertSettings
from .repository import AlertSettingsRepository

SECTION_KEY = "price"

PRICE_ALERTS_HELP = (
    "<b>Как это работает</b>\n\n"
    "Бот отслеживает цены облигаций из вашего портфеля и присылает уведомление, "
    "когда цена изменяется сильнее заданного порога.\n\n"
    "Включите мониторинг и при желании настройте пороги умеренного и сильного "
    "движения цены — отдельно для падения и роста."
)


def build_text(settings: PriceAlertSettings) -> str:
    """Собирает HTML-описание раздела с текущим статусом и порогами."""
    status = "включен" if settings.alerts_enabled else "выключен"
    text = (
        "<b>Мониторинг цен облигаций</b>\n\n"
        "Получайте уведомления при значительных изменениях цен облигаций "
        "в вашем портфеле.\n\n"
        f"Статус: <b>{status}</b>"
    )
    if settings.alerts_enabled:
        text += (
            "\n\n<b>Текущие пороги:</b>\n\n"
            "Падение:\n"
            f"  • Умеренное: {settings.drop_warning_threshold}%\n"
            f"  • Сильное: {settings.drop_critical_threshold}%\n\n"
            "Рост:\n"
            f"  • Умеренное: {settings.rise_warning_threshold}%\n"
            f"  • Сильное: {settings.rise_critical_threshold}%"
        )
    return text


async def render(telegram_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Экран раздела цен: описание + тумблер/пороги + «Назад»."""
    settings = await AlertSettingsRepository.get_or_create(telegram_id)
    builder = create_price_alerts_keyboard(settings.alerts_enabled)
    builder.row(back_to_hub_button())
    builder.row(help_button(SECTION_KEY))

    if settings.alerts_enabled:
        builder.adjust(1, 1, 2)
    else:
        builder.adjust(1, 2)
    return build_text(settings), builder.as_markup()


async def status_badge(telegram_id: int) -> str:
    """Бейдж для хаба: ✅ если мониторинг включён."""
    settings = await AlertSettingsRepository.get_or_create(telegram_id)
    return status_text(settings.alerts_enabled)


SECTION = MenuSection(
    key=SECTION_KEY,
    title="Мониторинг цен",
    render=render,
    status_badge=status_badge,
    help_text=PRICE_ALERTS_HELP,
)
