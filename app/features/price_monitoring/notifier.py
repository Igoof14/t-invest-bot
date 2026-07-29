"""Отправка уведомлений об аномалиях через Telegram-бота."""

import logging
from collections.abc import Sequence

from aiogram import Bot
from common.delivery import DeliveryResult, deliver
from common.scope import AlertScope

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

    async def send_single(
        self,
        telegram_id: int,
        anomaly: PriceAnomaly,
        *,
        scope: AlertScope = AlertScope.PORTFOLIO,
    ) -> DeliveryResult:
        """Отправляет одно уведомление.

        Returns:
            Итог доставки: см. ``DeliveryOutcome``.

        """
        message = format_single_alert(anomaly, scope)
        return await deliver(
            lambda: self._bot.send_message(telegram_id, message, parse_mode="HTML"),
            telegram_id=telegram_id,
            kind="price",
            items=1,
            isin=anomaly.isin,
            alert_type=anomaly.alert_type.value,
            scope=scope.value,
        )

    async def send_aggregated(
        self,
        telegram_id: int,
        anomalies: Sequence[PriceAnomaly],
        *,
        max_per_severity: int,
        scope: AlertScope = AlertScope.PORTFOLIO,
    ) -> DeliveryResult:
        """Отправляет сводное уведомление по нескольким аномалиям.

        Returns:
            Итог доставки: см. ``DeliveryOutcome``.

        """
        message, shown = format_aggregated_alert(
            anomalies, max_per_severity=max_per_severity, scope=scope
        )
        return await deliver(
            lambda: self._bot.send_message(telegram_id, message, parse_mode="HTML"),
            telegram_id=telegram_id,
            kind="price",
            items=len(anomalies),
            shown=len(shown),
            aggregated=True,
            scope=scope.value,
        )
