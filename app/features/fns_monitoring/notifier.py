"""Отправка уведомлений о блокировках счетов ФНС через Telegram-бота."""

from __future__ import annotations

import logging

from aiogram import Bot
from common.delivery import DeliveryOutcome, DeliveryResult, deliver
from common.scope import AlertScope

from .events import UserBlockAlert
from .formatter import format_fns_alert

logger = logging.getLogger(__name__)


class FnsBlockNotifier:
    """Отправляет пользователю сообщение о блокировках счетов по его бумагам."""

    def __init__(self, bot: Bot) -> None:
        """Инициализирует notifier."""
        self._bot = bot

    async def send(
        self,
        telegram_id: int,
        alerts: list[UserBlockAlert],
        *,
        scope: AlertScope = AlertScope.PORTFOLIO,
    ) -> DeliveryResult:
        """Отправляет одно сообщение со всеми блокировками пользователя.

        Returns:
            Итог доставки: см. ``DeliveryOutcome``.

        """
        if not alerts:
            return DeliveryResult(DeliveryOutcome.SENT)

        message = format_fns_alert(alerts, scope)

        return await deliver(
            lambda: self._bot.send_message(
                telegram_id,
                message,
                parse_mode="HTML",
                disable_web_page_preview=True,
            ),
            telegram_id=telegram_id,
            kind="fns",
            items=len(alerts),
            scope=scope.value,
        )
