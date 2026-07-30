"""Клавиатуры хаба меню и общие навигационные кнопки."""

from __future__ import annotations

import asyncio
import logging

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from core.clients.backend import users as users_api

from .callbacks import MenuCallback
from .registry import MenuSection

logger = logging.getLogger(__name__)

# Ключ корневого экрана хаба.
HUB_KEY = "hub"
HUB_TITLE = "<b>🔔 Уведомления</b>\n\nВыберите раздел:"

# Приписка, когда настройки не удалось прочитать: экран показывает дефолты, и
# без этой строки он уверенно врал бы подписанному пользователю «Выключено 🔕».
STALE_NOTE = (
    "\n\n⚠️ <i>Не удалось загрузить ваши настройки — показано состояние "
    "по умолчанию. Попробуйте открыть раздел позже.</i>"
)

# Приписка для пользователей без токена: объясняет текущий режим и апселл.
MARKET_MODE_NOTE = (
    "\n\n📡 <i>Сейчас вы получаете события по всему рынку. "
    "Подключите токен — останутся только ваши бумаги.</i>"
)


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


async def _no_badge() -> str:
    """Заглушка для секций без бейджа: держит порядок результатов ``gather``."""
    return ""


async def _has_token(telegram_id: int) -> bool:
    """Подключён ли токен.

    Идёт в клиент бэкенда напрямую, а не через ``BotUserRepository``: тот
    гасит ``BackendError`` и возвращает ``None``, что неотличимо от «токена
    нет». Здесь разница принципиальна — при сбое бэкенда мы предпочитаем не
    показать подсказку, чем предложить подключить токен тому, у кого он уже
    есть. Исключение ловит ``gather`` в :func:`build_hub`.
    """
    return await users_api.get_token(telegram_id) is not None


async def build_hub(
    telegram_id: int, sections: list[MenuSection]
) -> tuple[str, InlineKeyboardMarkup]:
    """Собирает экран хаба: строка-кнопка на каждую секцию с бейджем статуса.

    Бейджи запрашиваются параллельно: каждая секция самостоятельно ходит в БД
    за своими настройками, последовательный цикл складывал их задержки.
    Сбой одной секции не должен ронять весь экран — такая секция просто
    остаётся без бейджа.

    Проверка токена едет тем же ``gather``: она нужна только для подсказки о
    режиме, и отдельный последовательный round-trip ради неё был бы лишним.
    """
    *badges, token_state = await asyncio.gather(
        *(
            section.status_badge(telegram_id) if section.status_badge is not None else _no_badge()
            for section in sections
        ),
        _has_token(telegram_id),
        return_exceptions=True,
    )

    builder = InlineKeyboardBuilder()
    for section, result in zip(sections, badges, strict=True):
        if isinstance(result, BaseException):
            logger.error(f"Не удалось получить бейдж секции {section.key}: {result}")
            badge = ""
        else:
            badge = result
        builder.add(
            InlineKeyboardButton(
                text=f"{section.title}{f': {badge}' if badge else ''}",
                callback_data=MenuCallback(section=section.key).pack(),
            )
        )

    title = HUB_TITLE
    if token_state is False:
        # Отложенный импорт: разрывает цикл menu -> users -> base -> menu.
        from features.users.enums import SettingsButtonTexts, SettingsCallbackData

        title += MARKET_MODE_NOTE
        builder.add(
            InlineKeyboardButton(
                text=SettingsButtonTexts.ADD_TOKEN.value,
                callback_data=SettingsCallbackData.ADD_TOKEN.value,
            )
        )

    builder.adjust(1)
    return title, builder.as_markup()
