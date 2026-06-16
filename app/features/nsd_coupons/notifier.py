"""Отправка уведомлений о невыплаченных купонах через Telegram-бота."""

from __future__ import annotations

import logging

from aiogram import Bot

from .formatter import format_coupon_miss
from .schemas import CouponMissAlert

logger = logging.getLogger(__name__)


class NsdCouponNotifier:
    """Отправляет пользователю сообщение о неполученном купоне по его бумаге."""

    def __init__(self, bot: Bot) -> None:
        """Инициализирует notifier."""
        self._bot = bot

    async def send(self, telegram_id: int, alert: CouponMissAlert) -> bool:
        """Отправляет уведомление о невыплаченном купоне.

        Args:
            telegram_id: Telegram ID получателя.
            alert: Данные о невыплаченном купоне.

        Returns:
            ``True`` при успешной отправке, ``False`` при ошибке.
        """
        message = format_coupon_miss(alert)
        try:
            await self._bot.send_message(
                telegram_id,
                message,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            logger.info(
                "Уведомление о купоне %s №%d отправлено %s",
                alert.isin,
                alert.coupon_number,
                telegram_id,
            )
            return True
        except Exception as e:  # noqa: BLE001 — Telegram может заблокировать бота
            logger.error("Ошибка отправки уведомления о купоне %s: %s", telegram_id, e)
            return False
