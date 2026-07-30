"""Настройки уведомлений об офертах — через API бэкенда.

Таблицей `offer_alert_settings` владеет `bondelo-backend`, своей модели у бота нет.
Ошибка бэкенда не роняет хендлер: чтение отдаёт дефолты (всё выключено), запись
возвращает False.
"""

import logging

from core.clients.backend import notifications as api
from core.clients.backend.errors import BackendError
from core.clients.backend.notifications import OfferAlertSettings

logger = logging.getLogger(__name__)


class OfferSettingsRepository:
    """Доступ к настройкам уведомлений об офертах."""

    @classmethod
    async def get(cls, telegram_id: int) -> OfferAlertSettings:
        """Возвращает настройки пользователя; если он их не трогал — дефолтные."""
        try:
            return (await api.get_settings(telegram_id)).offers
        except BackendError as e:
            logger.error(f"Ошибка при получении настроек об офертах {telegram_id}: {e}")
            return OfferAlertSettings(stale=True)

    @classmethod
    async def update(cls, telegram_id: int, **fields: object) -> bool:
        """Обновляет переданные поля настроек, остальные оставляет как есть."""
        try:
            await api.update_offers(telegram_id, **fields)
        except BackendError as e:
            logger.error(f"Ошибка при обновлении настроек об офертах {telegram_id}: {e}")
            return False
        logger.info(f"Обновлены настройки уведомлений об офертах {telegram_id}")
        return True

    @classmethod
    async def toggle_alerts(cls, telegram_id: int) -> bool:
        """Переключает флаг alerts_enabled и возвращает новое значение.

        Raises:
            BackendError: Бэкенд недоступен — хендлер покажет ошибку, а не
                соврёт пользователю про переключённое состояние.

        """
        return await api.toggle(telegram_id, "offers")
