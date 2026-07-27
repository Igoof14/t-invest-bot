"""Отправка уведомлений об офертах через Telegram-бота."""

from __future__ import annotations

import logging

from aiogram import Bot
from common.delivery import DeliveryOutcome, DeliveryResult, deliver

from .formatter import format_offer_alerts
from .schemas import BondOffer

logger = logging.getLogger(__name__)


class OfferAlertNotifier:
    """Отправляет пользователю сообщение с перечнем приближающихся оферт."""

    def __init__(self, bot: Bot) -> None:
        """Инициализирует notifier.

        Args:
            bot: Экземпляр aiogram-бота.

        """
        self._bot = bot

    async def send(self, telegram_id: int, offers: list[BondOffer]) -> DeliveryResult:
        """Отправляет одно сообщение со всеми офертами пользователя.

        Args:
            telegram_id: Telegram ID получателя.
            offers: Список оферт для уведомления.

        Returns:
            Итог доставки: см. ``DeliveryOutcome``.

        """
        if not offers:
            return DeliveryResult(DeliveryOutcome.SENT)

        message = format_offer_alerts(offers)

        return await deliver(
            lambda: self._bot.send_message(
                telegram_id,
                message,
                parse_mode="HTML",
                disable_web_page_preview=True,
            ),
            telegram_id=telegram_id,
            kind="offer",
            items=len(offers),
        )
