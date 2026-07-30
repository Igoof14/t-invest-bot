"""Подписки на уведомления о блокировках ФНС — через API бэкенда.

Таблицей `fns_alert_settings` владеет `bondelo-backend`, своей модели у бота нет.
Состояние дедупа блокировок (`fns_blocking_records`) принадлежит сервису
`fns-monitoring` — бот его не ведёт.
"""

from __future__ import annotations

import logging

from core.clients.backend import notifications as api
from core.clients.backend.errors import BackendError
from core.clients.backend.notifications import FnsAlertSettings

logger = logging.getLogger(__name__)


class FnsAlertSettingsRepository:
    """Доступ к подпискам пользователей на уведомления о блокировках ФНС."""

    @classmethod
    async def toggle(cls, telegram_id: int) -> bool:
        """Переключает подписку пользователя и возвращает новое состояние.

        Raises:
            BackendError: Бэкенд недоступен — хендлер покажет ошибку, а не
                соврёт пользователю про переключённое состояние.

        """
        return await api.toggle(telegram_id, "fns")

    @classmethod
    async def get(cls, telegram_id: int) -> FnsAlertSettings:
        """Возвращает подписку; при ошибке бэкенда — дефолт с меткой ``stale``."""
        try:
            enabled = (await api.get_settings(telegram_id)).fns_enabled
        except BackendError as e:
            logger.error(f"Ошибка при получении подписки ФНС {telegram_id}: {e}")
            return FnsAlertSettings(stale=True)
        return FnsAlertSettings(alerts_enabled=enabled)
