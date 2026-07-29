"""Отправка уведомлений об изменении рейтингов через Telegram-бота."""

from __future__ import annotations

import logging

from aiogram import Bot
from common.delivery import DeliveryOutcome, DeliveryResult, deliver
from common.scope import AlertScope

from .formatter import format_rating_alert
from .schemas import RatingChange

logger = logging.getLogger(__name__)


class RatingAlertNotifier:
    """Отправляет пользователю сообщение об изменениях рейтингов."""

    def __init__(self, bot: Bot) -> None:
        """Инициализирует notifier.

        Args:
            bot: Экземпляр aiogram-бота.

        """
        self._bot = bot

    async def send(
        self,
        telegram_id: int,
        changes: list[RatingChange],
        *,
        scope: AlertScope = AlertScope.PORTFOLIO,
    ) -> DeliveryResult:
        """Отправляет одно сообщение со всеми изменениями рейтингов.

        Returns:
            Итог доставки: см. ``DeliveryOutcome``.

        """
        if not changes:
            return DeliveryResult(DeliveryOutcome.SENT)

        message = format_rating_alert(changes, scope)

        return await deliver(
            lambda: self._bot.send_message(
                telegram_id,
                message,
                parse_mode="HTML",
                disable_web_page_preview=True,
            ),
            telegram_id=telegram_id,
            kind="rating",
            items=len(changes),
            scope=scope.value,
        )
