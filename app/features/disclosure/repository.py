"""Подписки на уведомления о раскрытиях — через API бэкенда.

Таблицей `disclosure_alert_settings` владеет `bondelo-backend`, своей модели у
бота нет. Разбор раскрытий и рассылку ведёт `disclosure-parsing-worker` — он же
читает эти настройки напрямую, когда решает, кому слать алерт.
"""

from __future__ import annotations

import logging

from core.clients.backend import notifications as api
from core.clients.backend.errors import BackendError
from core.clients.backend.notifications import DisclosureAlertSettings

logger = logging.getLogger(__name__)


class DisclosureAlertSettingsRepository:
    """Доступ к подпискам пользователей на уведомления о раскрытиях."""

    @classmethod
    async def toggle(cls, telegram_id: int) -> bool:
        """Переключает подписку пользователя и возвращает новое состояние.

        Raises:
            BackendError: Бэкенд недоступен — хендлер покажет ошибку, а не
                соврёт пользователю про переключённое состояние.

        """
        return await api.toggle(telegram_id, "disclosure")

    @classmethod
    async def set_min_risk_level(cls, telegram_id: int, level: str) -> DisclosureAlertSettings:
        """Ставит минимальный уровень риска, при котором приходит уведомление.

        Raises:
            BackendError: Бэкенд недоступен.

        """
        return await api.update_disclosure(telegram_id, min_risk_level=level)

    @classmethod
    async def get(cls, telegram_id: int) -> DisclosureAlertSettings:
        """Возвращает настройки раскрытий; при ошибке бэкенда — дефолты."""
        try:
            return (await api.get_settings(telegram_id)).disclosure
        except BackendError as e:
            logger.error(f"Ошибка при получении настроек раскрытий {telegram_id}: {e}")
            return DisclosureAlertSettings(stale=True)
