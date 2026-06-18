"""Схемы и callback-константы админской рассылки."""

from __future__ import annotations

from dataclasses import dataclass

# Callback-данные кнопок подтверждения рассылки.
BROADCAST_CONFIRM = "bc:send"
BROADCAST_CANCEL = "bc:cancel"


@dataclass(frozen=True, slots=True)
class BroadcastResult:
    """Итог рассылки.

    Attributes:
        delivered: Сколько сообщений доставлено.
        blocked: Сколько пользователей заблокировали бота (деактивированы).
        failed: Сколько отправок не удалось по прочим причинам.

    """

    delivered: int = 0
    blocked: int = 0
    failed: int = 0
