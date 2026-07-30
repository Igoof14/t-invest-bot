"""Реестр секций меню.

Каждая фича регистрирует свою секцию — хаб «Уведомления» подхватывает её
автоматически. Добавление фичи не требует правок самого хаба.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from aiogram.types import InlineKeyboardMarkup
from core.clients.backend.notifications import NotificationSettings

# (telegram_id) -> (текст экрана, инлайн-клавиатура секции).
RenderFn = Callable[[int], Awaitable[tuple[str, InlineKeyboardMarkup]]]
# (снимок настроек уведомлений) -> бейдж статуса для хаба.
#
# Бейдж не ходит в сеть: хаб читает настройки всех секций одним запросом и
# раздаёт снимок. Раньше каждая секция запрашивала их сама, хотя эндпоинт
# отдаёт их целиком — пять одинаковых round-trip'ов на один экран.
BadgeFn = Callable[[NotificationSettings], str]


@dataclass(frozen=True)
class MenuSection:
    """Описание раздела меню, предоставляемое фичей."""

    key: str
    title: str
    render: RenderFn
    status_badge: BadgeFn | None = None
    # HTML-описание «как это работает». Если задано — на экране секции
    # появляется кнопка, открывающая его (с возвратом к секции).
    help_text: str | None = None


_SECTIONS: list[MenuSection] = []


def register_section(section: MenuSection) -> None:
    """Регистрирует секцию (идемпотентно по ключу)."""
    if any(existing.key == section.key for existing in _SECTIONS):
        return
    _SECTIONS.append(section)


def get_sections() -> list[MenuSection]:
    """Возвращает все зарегистрированные секции в порядке регистрации."""
    return list(_SECTIONS)


def get_section(key: str) -> MenuSection | None:
    """Возвращает секцию по ключу или ``None``."""
    return next((section for section in _SECTIONS if section.key == key), None)
