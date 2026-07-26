"""Клавиатуры хаба меню и общие навигационные кнопки."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .callbacks import MenuCallback
from .registry import MenuSection

# Ключ корневого экрана хаба.
HUB_KEY = "hub"
HUB_TITLE = "<b>🔔 Уведомления</b>\n\nВыберите раздел:"


def status_text(enabled: bool) -> str:
    """Бейдж статуса секции для хаба: «Включено 🔔» / «Выключено 🔕»."""
    return "Включено 🔔" if enabled else "Выключено 🔕"


def nav_button(section: str, text: str = "⬅️ Назад", action: str = "open") -> InlineKeyboardButton:
    """Кнопка перехода к указанной секции/экрану меню."""
    return InlineKeyboardButton(
        text=text, callback_data=MenuCallback(section=section, action=action).pack()
    )


def back_to_hub_button() -> InlineKeyboardButton:
    """Кнопка «Назад» в хаб «Уведомления»."""
    return nav_button(HUB_KEY)


def help_button(section: str) -> InlineKeyboardButton:
    """Кнопка «Как это работает» для экрана секции."""
    return nav_button(section, text="Как это работает", action="help")


def build_help(section: MenuSection) -> tuple[str, InlineKeyboardMarkup]:
    """Экран описания секции: текст «как это работает» + «Назад» к секции."""
    builder = InlineKeyboardBuilder()
    builder.row(nav_button(section.key))
    return section.help_text or "", builder.as_markup()


async def build_hub(
    telegram_id: int, sections: list[MenuSection]
) -> tuple[str, InlineKeyboardMarkup]:
    """Собирает экран хаба: строка-кнопка на каждую секцию с бейджем статуса."""
    builder = InlineKeyboardBuilder()
    for section in sections:
        badge = ""
        if section.status_badge is not None:
            badge = f": {await section.status_badge(telegram_id)}"
        builder.add(
            InlineKeyboardButton(
                text=f"{section.title}{badge}",
                callback_data=MenuCallback(section=section.key).pack(),
            )
        )
    builder.adjust(1)
    return HUB_TITLE, builder.as_markup()
