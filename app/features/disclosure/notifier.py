"""Отправка уведомлений о раскрытиях эмитентов через Telegram-бота."""

from __future__ import annotations

import logging

from aiogram import Bot
from common.delivery import DeliveryOutcome, DeliveryResult, deliver
from common.scope import AlertScope

from .formatter import format_disclosure_alert
from .schemas import DisclosureAlert

logger = logging.getLogger(__name__)


class DisclosureAlertNotifier:
    """Отправляет пользователю сообщение о раскрытиях эмитента."""

    def __init__(self, bot: Bot) -> None:
        """Инициализирует notifier.

        Args:
            bot: Экземпляр aiogram-бота.

        """
        self._bot = bot

    async def send(
        self,
        telegram_id: int,
        alerts: list[DisclosureAlert],
        *,
        scope: AlertScope = AlertScope.PORTFOLIO,
    ) -> DeliveryResult:
        """Отправляет одно сообщение со всеми раскрытиями.

        Returns:
            Итог доставки: см. ``DeliveryOutcome``.

        """
        if not alerts:
            return DeliveryResult(DeliveryOutcome.SENT)

        message = format_disclosure_alert(alerts, scope)

        return await deliver(
            lambda: self._bot.send_message(
                telegram_id,
                message,
                parse_mode="HTML",
                disable_web_page_preview=True,
            ),
            telegram_id=telegram_id,
            kind="disclosure",
            items=len(alerts),
            scope=scope.value,
        )
