"""Отправка уведомлений о блокировках счетов ФНС через Telegram-бота."""

from __future__ import annotations

import logging

from aiogram import Bot

from .events import UserBlockAlert
from .formatter import format_fns_alert

logger = logging.getLogger(__name__)


class FnsBlockNotifier:
    """Отправляет пользователю сообщение о блокировках счетов по его бумагам."""

    def __init__(self, bot: Bot) -> None:
        """Инициализирует notifier."""
        self._bot = bot

    async def send(self, telegram_id: int, alerts: list[UserBlockAlert]) -> bool:
        """Отправляет одно сообщение со всеми блокировками пользователя.

        Returns:
            True при успешной отправке, False при ошибке.

        """
        if not alerts:
            return True

        message = format_fns_alert(alerts)

        try:
            await self._bot.send_message(
                telegram_id,
                message,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            logger.info(
                f"Отправлено уведомление о блокировках ФНС пользователю "
                f"{telegram_id}: {len(alerts)} эмитент(ов)"
            )
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления ФНС {telegram_id}: {e}")
            return False
