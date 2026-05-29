"""Отправка уведомлений об офертах через Telegram-бота."""

from __future__ import annotations

import logging

from aiogram import Bot
from core.clients.moex.moex_bonds import MoexBondOffer

from .formatter import format_offer_alerts

logger = logging.getLogger(__name__)


class OfferAlertNotifier:
    """Отправляет пользователю сообщение с перечнем приближающихся оферт."""

    def __init__(self, bot: Bot) -> None:
        """Инициализирует notifier.

        Args:
            bot: Экземпляр aiogram-бота.

        """
        self._bot = bot

    async def send(self, telegram_id: int, offers: list[MoexBondOffer]) -> bool:
        """Отправляет одно сообщение со всеми офертами пользователя.

        Args:
            telegram_id: Telegram ID получателя.
            offers: Список оферт для уведомления.

        Returns:
            True при успешной отправке, False при ошибке.

        """
        if not offers:
            return True

        message = format_offer_alerts(offers)

        try:
            await self._bot.send_message(
                telegram_id,
                message,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            logger.info(
                f"Отправлено уведомление об офертах пользователю {telegram_id}: "
                f"{len(offers)} оферт(ы)"
            )
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления пользователю {telegram_id}: {e}")
            return False
