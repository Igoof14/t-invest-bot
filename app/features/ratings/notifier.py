"""Отправка уведомлений об изменении рейтингов через Telegram-бота."""

from __future__ import annotations

import logging

from aiogram import Bot

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

    async def send(self, telegram_id: int, changes: list[RatingChange]) -> bool:
        """Отправляет одно сообщение со всеми изменениями рейтингов.

        Returns:
            True при успешной отправке, False при ошибке.

        """
        if not changes:
            return True

        message = format_rating_alert(changes)

        try:
            await self._bot.send_message(
                telegram_id,
                message,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            logger.info(
                f"Отправлено уведомление о рейтингах пользователю {telegram_id}: "
                f"{len(changes)} изменений"
            )
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления о рейтингах {telegram_id}: {e}")
            return False
