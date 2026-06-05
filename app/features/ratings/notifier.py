"""Отправка уведомлений об изменении рейтинга через Telegram-бота (общее)."""

from __future__ import annotations

import logging

from aiogram import Bot

from .events import RatingChange
from .formatter import format_rating_alert

logger = logging.getLogger(__name__)


class RatingAlertNotifier:
    """Отправляет пользователю сообщение об изменениях рейтинга по его бумагам."""

    def __init__(self, bot: Bot) -> None:
        """Инициализирует notifier."""
        self._bot = bot

    async def send(
        self, telegram_id: int, agency_name: str, changes: list[RatingChange]
    ) -> bool:
        """Отправляет одно сообщение со всеми изменениями рейтинга пользователя.

        Returns:
            True при успешной отправке, False при ошибке.

        """
        if not changes:
            return True

        message = format_rating_alert(agency_name, changes)

        try:
            await self._bot.send_message(
                telegram_id,
                message,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            logger.info(
                f"Отправлено уведомление об изменении рейтинга пользователю "
                f"{telegram_id}: {len(changes)} изменени(й)"
            )
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления пользователю {telegram_id}: {e}")
            return False
