"""Отправка уведомлений об аномалиях через Telegram-бота."""

import logging
from collections.abc import Sequence

from aiogram import Bot

from .formatter import format_aggregated_alert, format_single_alert
from .schemas import PriceAnomaly

logger = logging.getLogger(__name__)


class PriceAlertNotifier:
    """Отправляет сообщения об аномалиях цен пользователю.

    Дедупликация и антиспам выполняются сервисом-продюсером событий —
    notifier только доставляет сообщения.
    """

    def __init__(self, bot: Bot):
        """Инициализирует notifier.

        Args:
            bot: Экземпляр aiogram-бота.

        """
        self._bot = bot

    async def send_single(self, telegram_id: int, anomaly: PriceAnomaly) -> bool:
        """Отправляет одно уведомление.

        Returns:
            True при успешной отправке, False при ошибке.

        """
        message = format_single_alert(anomaly)
        try:
            await self._bot.send_message(telegram_id, message, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Ошибка при отправке алерта пользователю {telegram_id}: {e}")
            return False

        logger.info(
            f"Отправлен алерт пользователю {telegram_id}: "
            f"{anomaly.ticker} {anomaly.alert_type.value}"
        )
        return True

    async def send_aggregated(
        self,
        telegram_id: int,
        anomalies: Sequence[PriceAnomaly],
        *,
        max_per_severity: int,
    ) -> bool:
        """Отправляет сводное уведомление по нескольким аномалиям.

        Returns:
            True при успешной отправке, False при ошибке.

        """
        message, shown = format_aggregated_alert(anomalies, max_per_severity=max_per_severity)
        try:
            await self._bot.send_message(telegram_id, message, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Ошибка при отправке сводного алерта пользователю {telegram_id}: {e}")
            return False

        logger.info(
            f"Отправлен сводный алерт пользователю {telegram_id}: "
            f"показано {len(shown)} из {len(anomalies)} аномалий"
        )
        return True
