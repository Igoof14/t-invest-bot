"""Настройки уведомлений о ценах — через API бэкенда.

Таблицей `price_alert_settings` владеет `bondelo-backend`, своей модели у бота нет.
Ошибка бэкенда не роняет хендлер: чтение отдаёт дефолты (всё выключено), запись
возвращает False.
"""

import logging

from core.clients.backend import notifications as api
from core.clients.backend.errors import BackendError
from core.clients.backend.notifications import PriceAlertSettings

logger = logging.getLogger(__name__)


class AlertSettingsRepository:
    """Доступ к настройкам уведомлений о ценах."""

    @classmethod
    async def get(cls, telegram_id: int) -> PriceAlertSettings:
        """Возвращает настройки пользователя; если он их не трогал — дефолтные."""
        try:
            return (await api.get_settings(telegram_id)).prices
        except BackendError as e:
            logger.error(f"Ошибка при получении настроек о ценах {telegram_id}: {e}")
            return PriceAlertSettings(stale=True)

    @classmethod
    async def update(cls, telegram_id: int, **fields: object) -> bool:
        """Обновляет переданные пороги, остальные оставляет как есть."""
        try:
            await api.update_prices(telegram_id, **fields)
        except BackendError as e:
            logger.error(f"Ошибка при обновлении настроек о ценах {telegram_id}: {e}")
            return False
        logger.info(f"Обновлены настройки уведомлений о ценах {telegram_id}")
        return True

    @classmethod
    async def toggle_alerts(cls, telegram_id: int) -> bool:
        """Переключает флаг alerts_enabled и возвращает новое значение.

        Raises:
            BackendError: Бэкенд недоступен — хендлер покажет ошибку, а не
                соврёт пользователю про переключённое состояние.

        """
        return await api.toggle(telegram_id, "prices")
