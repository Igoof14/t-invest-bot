"""Клавиатуры хаба меню и общие навигационные кнопки."""

from __future__ import annotations

import asyncio
import logging

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from core.clients.backend import notifications as notifications_api
from core.clients.backend import users as users_api
from core.clients.backend.errors import BackendError
from core.clients.backend.notifications import NotificationSettings
from core.config import config

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

# Приписка для хаба, когда настройки не прочитались: бейджи не показываем совсем.
# Соврать подписанному пользователю «Выключено 🔕» хуже, чем не показать статус.
HUB_STALE_NOTE = (
    "\n\n⚠️ <i>Не удалось загрузить статусы разделов. "
    "Откройте раздел, чтобы увидеть текущие настройки.</i>"
)

# Приписка для пользователей без токена: объясняет текущий режим и апселл.
MINIAPP_BUTTON_TEXT = "Открыть приложение"

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


async def _notification_settings(telegram_id: int) -> NotificationSettings | None:
    """Настройки всех секций одним запросом; ``None`` — бэкенд не ответил.

    Раньше за настройками ходила каждая секция отдельно, хотя эндпоинт отдаёт их
    целиком: пять одинаковых round-trip'ов на один экран.
    """
    try:
        return await notifications_api.get_settings(telegram_id)
    except BackendError as e:
        logger.error(f"Не удалось получить настройки уведомлений {telegram_id}: {e}")
        return None


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

    Настройки всех секций читаются одним запросом, а бейджи считаются из этого
    снимка: эндпоинт отдаёт разделы целиком, поэтому пять секций, ходивших за
    ними по отдельности, повторяли один и тот же round-trip. Если запрос не
    удался, бейджей нет ни у одной секции — статус лучше не показать, чем
    показать неверный.

    Проверка токена едет тем же ``gather``: она нужна только для подсказки о
    режиме, и отдельный последовательный round-trip ради неё был бы лишним.
    """
    settings, token_state = await asyncio.gather(
        _notification_settings(telegram_id),
        _has_token(telegram_id),
        return_exceptions=True,
    )
    if isinstance(settings, BaseException):
        # BackendError гасит сам ``_notification_settings``; сюда попадает только
        # неожидаемое — экран всё равно рисуем, но без бейджей.
        logger.error(f"Неожиданная ошибка чтения настроек {telegram_id}: {settings}")
        settings = None

    builder = InlineKeyboardBuilder()
    for section in sections:
        badge = ""
        if section.status_badge is not None and settings is not None:
            try:
                badge = section.status_badge(settings)
            except Exception as e:
                # Сбой одной секции не должен ронять весь экран — она просто
                # остаётся без бейджа.
                logger.error(f"Не удалось получить бейдж секции {section.key}: {e}")
        builder.add(
            InlineKeyboardButton(
                text=f"{section.title}{f': {badge}' if badge else ''}",
                callback_data=MenuCallback(section=section.key).pack(),
            )
        )

    # Кнопка запуска мини-аппа. Появляется, только когда фронтенд задеплоен и
    # его адрес задан: меню бота остаётся полноценным и без неё.
    if config.miniapp_url:
        builder.add(
            InlineKeyboardButton(
                text=MINIAPP_BUTTON_TEXT,
                web_app=WebAppInfo(url=config.miniapp_url),
            )
        )

    title = HUB_TITLE
    if settings is None:
        title += HUB_STALE_NOTE
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
