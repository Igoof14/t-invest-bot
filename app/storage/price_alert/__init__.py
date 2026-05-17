"""Хранилище данных мониторинга цен облигаций.

Этот пакет предоставляет три репозитория:
- :class:`AlertSettingsRepository` — настройки уведомлений пользователя;
- :class:`PriceHistoryRepository` — снимки цен облигаций;
- :class:`SentAlertRepository` — учёт отправленных алертов (anti-spam).

Для обратной совместимости со старым кодом экспортируется фасад
:class:`PriceAlertStorage`, делегирующий вызовы в соответствующие репозитории.
"""

from collections.abc import Iterable
from typing import TYPE_CHECKING

from .price_history_repo import PriceHistoryRepository
from .sent_alert_repo import SentAlertRepository
from .settings_repo import AlertSettingsRepository

if TYPE_CHECKING:
    from invest.portfolio_prices import BondPrice
    from models.alerts import PriceAlertSettings


# Константы политики антиспама. На Этапе 4 переедут в services/price_alert/config.py.
ALERT_COOLDOWN_HOURS = 4
MAX_DAILY_ALERTS = 10


class PriceAlertStorage:
    """Фасад над репозиториями для обратной совместимости.

    Новый код должен использовать репозитории напрямую:
    ``AlertSettingsRepository``, ``PriceHistoryRepository``, ``SentAlertRepository``.
    """

    # --- Настройки пользователя ---

    @classmethod
    async def get_user_settings(cls, telegram_id: int) -> "PriceAlertSettings | None":
        """См. AlertSettingsRepository.get."""
        return await AlertSettingsRepository.get(telegram_id)

    @classmethod
    async def get_or_create_user_settings(cls, telegram_id: int) -> "PriceAlertSettings":
        """См. AlertSettingsRepository.get_or_create."""
        return await AlertSettingsRepository.get_or_create(telegram_id)

    @classmethod
    async def update_user_settings(cls, telegram_id: int, **fields: object) -> bool:
        """См. AlertSettingsRepository.update."""
        return await AlertSettingsRepository.update(telegram_id, **fields)

    @classmethod
    async def toggle_alerts(cls, telegram_id: int) -> bool:
        """См. AlertSettingsRepository.toggle_alerts."""
        return await AlertSettingsRepository.toggle_alerts(telegram_id)

    @classmethod
    async def get_all_users_with_alerts_enabled(cls) -> list[int]:
        """См. AlertSettingsRepository.list_users_with_alerts_enabled."""
        return await AlertSettingsRepository.list_users_with_alerts_enabled()

    # --- История цен ---

    @classmethod
    async def get_latest_prices(cls, telegram_id: int) -> "list[BondPrice]":
        """См. PriceHistoryRepository.get_latest."""
        return await PriceHistoryRepository.get_latest(telegram_id)

    @classmethod
    async def save_price_snapshot(cls, telegram_id: int, prices: "Iterable[BondPrice]") -> bool:
        """См. PriceHistoryRepository.save_snapshot."""
        return await PriceHistoryRepository.save_snapshot(telegram_id, prices)

    @classmethod
    async def cleanup_old_prices(cls, days_to_keep: int = 7) -> int:
        """См. PriceHistoryRepository.cleanup_older_than."""
        return await PriceHistoryRepository.cleanup_older_than(days_to_keep)

    # --- Anti-spam ---

    @classmethod
    async def record_sent_alert(cls, telegram_id: int, figi: str, alert_type: str) -> bool:
        """См. SentAlertRepository.record."""
        return await SentAlertRepository.record(telegram_id, figi, alert_type)

    @classmethod
    async def can_send_alert(cls, telegram_id: int, figi: str) -> bool:
        """Cooldown-проверка: можно ли отправить алерт по бумаге."""
        return not await SentAlertRepository.has_recent(
            telegram_id, figi, hours=ALERT_COOLDOWN_HOURS
        )

    @classmethod
    async def get_daily_alert_count(cls, telegram_id: int) -> int:
        """См. SentAlertRepository.count_today."""
        return await SentAlertRepository.count_today(telegram_id)

    @classmethod
    async def can_send_more_alerts_today(cls, telegram_id: int) -> bool:
        """Проверяет, не исчерпан ли дневной лимит отправок."""
        count = await SentAlertRepository.count_today(telegram_id)
        return count < MAX_DAILY_ALERTS

    @classmethod
    async def get_last_alert_type(cls, telegram_id: int, figi: str) -> str | None:
        """См. SentAlertRepository.last_alert_type."""
        return await SentAlertRepository.last_alert_type(telegram_id, figi)

    @classmethod
    async def cleanup_old_alerts(cls, days_to_keep: int = 7) -> int:
        """См. SentAlertRepository.cleanup_older_than."""
        return await SentAlertRepository.cleanup_older_than(days_to_keep)


__all__ = [
    "ALERT_COOLDOWN_HOURS",
    "MAX_DAILY_ALERTS",
    "AlertSettingsRepository",
    "PriceAlertStorage",
    "PriceHistoryRepository",
    "SentAlertRepository",
]
