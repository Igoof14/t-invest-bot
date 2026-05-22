"""Политика антиспама для уведомлений о ценах.

Правила:
1. Cooldown ``cooldown_hours`` часов между алертами по одной бумаге.
2. Эскалация: если последний алерт по бумаге был WARNING, а текущий CRITICAL
   в том же направлении (drop/rise), алерт пропускается даже внутри cooldown.
3. Не более ``max_daily_alerts`` уведомлений в сутки на пользователя.
"""

import logging
from collections.abc import Iterable

from .config import AlertPolicyConfig
from .domain import AlertSeverity, AlertType, PriceAnomaly
from .repository import SentAlertRepository

logger = logging.getLogger(__name__)


class AntiSpamPolicy:
    """Решает, какие из обнаруженных аномалий можно отправлять прямо сейчас."""

    def __init__(
        self,
        sent_repo: type[SentAlertRepository] = SentAlertRepository,
        config: AlertPolicyConfig | None = None,
    ):
        """Инициализирует политику.

        Args:
            sent_repo: Репозиторий отправленных алертов.
            config: Конфигурация политики. Если None — используется дефолтная.

        """
        from .config import DEFAULT_POLICY

        self._sent_repo = sent_repo
        self._config = config or DEFAULT_POLICY

    async def should_send(self, telegram_id: int, anomaly: PriceAnomaly) -> bool:
        """Проверяет, можно ли отправить конкретную аномалию."""
        # 1. Дневной лимит
        daily_count = await self._sent_repo.count_today(telegram_id)
        if daily_count >= self._config.max_daily_alerts:
            logger.debug(
                f"Дневной лимит алертов исчерпан для пользователя {telegram_id} "
                f"({daily_count}/{self._config.max_daily_alerts})"
            )
            return False

        # 2. Cooldown / эскалация
        is_in_cooldown = await self._sent_repo.has_recent(
            telegram_id, anomaly.figi, hours=self._config.cooldown_hours
        )
        if not is_in_cooldown:
            return True

        if await self._is_escalation(telegram_id, anomaly):
            logger.debug(f"Разрешаем эскалацию алерта для {anomaly.figi}")
            return True

        logger.debug(f"Cooldown активен для {anomaly.figi}")
        return False

    async def filter(
        self, telegram_id: int, anomalies: Iterable[PriceAnomaly]
    ) -> list[PriceAnomaly]:
        """Возвращает только те аномалии, которые можно отправить."""
        result: list[PriceAnomaly] = []
        for anomaly in anomalies:
            if await self.should_send(telegram_id, anomaly):
                result.append(anomaly)  # noqa: PERF401 — await в list-comp невозможен
        return result

    async def _is_escalation(self, telegram_id: int, anomaly: PriceAnomaly) -> bool:
        """Проверяет, является ли алерт эскалацией ``WARNING → CRITICAL``.

        Эскалация засчитывается, только если последний алерт по бумаге был
        WARNING в том же направлении (drop/rise), а текущий — CRITICAL.
        """
        if not anomaly.is_critical:
            return False

        last_raw = await self._sent_repo.last_alert_type(telegram_id, anomaly.figi)
        if last_raw is None:
            return False

        try:
            last_type = AlertType(last_raw)
        except ValueError:
            # Невалидное значение в БД — игнорируем.
            return False

        return (
            last_type.severity is AlertSeverity.WARNING and last_type.direction is anomaly.direction
        )
