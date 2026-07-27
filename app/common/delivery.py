"""Единая доставка исходящих сообщений: классификация ошибок и трекинг.

До появления этого модуля каждый ``features/*/notifier.py`` ловил
``Exception`` целиком и возвращал ``False``. Из-за этого
``TelegramForbiddenError`` (пользователь заблокировал бота) не отличался от
сетевой ошибки: пользователь не деактивировался, а endpoint отдавал 503, и
Cloud Tasks бесконечно ретраил заведомо невозможную отправку.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from features.analytics import Direction, EventName, track
from features.users.repository import BotUserRepository

logger = logging.getLogger(__name__)


class DeliveryOutcome(StrEnum):
    """Итог отправки одного сообщения."""

    SENT = "sent"
    """Доставлено."""

    BLOCKED = "blocked"
    """Пользователь заблокировал или удалил бота. Повтор бессмыслен."""

    FAILED = "failed"
    """Постоянная ошибка (например, некорректный запрос). Повтор бессмыслен."""

    RETRY = "retry"
    """Временная ошибка: сеть, 5xx, флуд-контроль. Повтор уместен."""


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    """Итог отправки с причиной для логов и аналитики."""

    outcome: DeliveryOutcome
    reason: str | None = None

    @property
    def is_sent(self) -> bool:
        """True, если сообщение доставлено."""
        return self.outcome is DeliveryOutcome.SENT

    @property
    def should_retry(self) -> bool:
        """True, если внешнему планировщику стоит повторить задачу."""
        return self.outcome is DeliveryOutcome.RETRY


def classify_send_error(exc: Exception) -> DeliveryResult:
    """Классифицирует исключение Telegram API.

    Args:
        exc: Исключение, поднятое методом отправки.

    Returns:
        Итог с причиной. ``BLOCKED``/``FAILED`` означают, что повторять не надо.

    """
    if isinstance(exc, TelegramForbiddenError):
        return DeliveryResult(DeliveryOutcome.BLOCKED, "blocked")
    if isinstance(exc, TelegramRetryAfter):
        return DeliveryResult(DeliveryOutcome.RETRY, "retry_after")
    if isinstance(exc, TelegramBadRequest):
        return DeliveryResult(DeliveryOutcome.FAILED, "bad_request")
    return DeliveryResult(DeliveryOutcome.RETRY, "transport")


async def deliver(
    send: Callable[[], Awaitable[Any]],
    *,
    telegram_id: int,
    kind: str,
    user_repo: type[BotUserRepository] = BotUserRepository,
    **props: Any,
) -> DeliveryResult:
    """Отправляет сообщение, классифицирует ошибку и трекает результат.

    При ``TelegramForbiddenError`` деактивирует пользователя — так же, как это
    делает ``BroadcastService``. При флуд-контроле ждёт указанное время и
    повторяет отправку один раз.

    Args:
        send: Корутина-фабрика самой отправки (обычно ``lambda:
            bot.send_message(...)``). Вызывается повторно при флуд-контроле.
        telegram_id: Получатель.
        kind: Тип уведомления для аналитики: ``price``, ``offer``, ``rating``,
            ``fns``.
        user_repo: Репозиторий пользователей (подменяется в тестах).
        **props: Дополнительные свойства события (например, ``items``).

    Returns:
        Итог доставки.

    """
    result = await _send_once(send, telegram_id=telegram_id, user_repo=user_repo)

    if result.outcome is DeliveryOutcome.RETRY and result.reason == "retry_after":
        # Флуд-контроль: подождали внутри _send_once, пробуем ровно один раз.
        result = await _send_once(send, telegram_id=telegram_id, user_repo=user_repo)

    if result.is_sent:
        logger.info(f"Уведомление {kind} доставлено пользователю {telegram_id}")
        await track(
            EventName.NOTIFICATION_SENT,
            telegram_id=telegram_id,
            action=kind,
            direction=Direction.OUT,
            kind=kind,
            **props,
        )
    else:
        logger.error(
            f"Уведомление {kind} не доставлено пользователю {telegram_id}: {result.reason}"
        )
        await track(
            EventName.NOTIFICATION_FAILED,
            telegram_id=telegram_id,
            action=kind,
            direction=Direction.OUT,
            kind=kind,
            reason=result.reason,
            **props,
        )

    return result


async def _send_once(
    send: Callable[[], Awaitable[Any]],
    *,
    telegram_id: int,
    user_repo: type[BotUserRepository],
) -> DeliveryResult:
    """Одна попытка отправки. При флуд-контроле выжидает паузу."""
    try:
        await send()
        return DeliveryResult(DeliveryOutcome.SENT)
    except Exception as e:
        result = classify_send_error(e)
        if result.outcome is DeliveryOutcome.BLOCKED:
            await user_repo.deactivate_user(telegram_id)
        elif result.reason == "retry_after" and isinstance(e, TelegramRetryAfter):
            logger.warning(f"Флуд-контроль {e.retry_after} сек для {telegram_id}")
            await asyncio.sleep(e.retry_after)
        return result
