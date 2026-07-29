"""Клавиатура настроек уведомлений о раскрытиях эмитентов."""

from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .enums import RISK_CHOICE_TITLES, RISK_ICONS
from .schemas import RISK_LEVELS, DisclosureAlertCallback


def create_disclosure_alerts_keyboard(enabled: bool, min_risk_level: str) -> InlineKeyboardBuilder:
    """Создаёт клавиатуру: тумблер подписки и выбор минимального уровня риска.

    Args:
        enabled: Включены ли уведомления у пользователя.
        min_risk_level: Текущий порог тяжести.

    Returns:
        Билдер с тумблером и — если подписка включена — кнопками порога.

    """
    builder = InlineKeyboardBuilder()
    mark = "Включено 🔔" if enabled else "Выключено 🔕"
    builder.row(
        InlineKeyboardButton(
            text=f"Раскрытия: {mark}",
            callback_data=DisclosureAlertCallback(action="toggle").pack(),
        )
    )

    # Выключенная секция не шлёт ничего, порог у неё нерелевантен.
    if not enabled:
        return builder

    for level in RISK_LEVELS:
        # Иконка уровня остаётся и у выбранного варианта: она показывает тяжесть,
        # а галочка в конце — что выбрано именно это. Раньше ✅ вставала вместо
        # иконки, и строка читалась как ещё одна иконка в общем ряду.
        selected = " ✅" if level == min_risk_level else ""
        builder.row(
            InlineKeyboardButton(
                text=f"{RISK_ICONS[level]} {RISK_CHOICE_TITLES[level]}{selected}",
                callback_data=DisclosureAlertCallback(action="level", level=level).pack(),
            )
        )
    return builder
