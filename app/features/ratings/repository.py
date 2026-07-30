"""Подписки на уведомления о рейтингах — через API бэкенда.

Таблицей `rating_alert_settings` владеет `bondelo-backend`, своей модели у бота нет.
Ошибка бэкенда не роняет хендлер: чтение отдаёт пустой набор подписок.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from core.clients.backend import notifications as api
from core.clients.backend.errors import BackendError

from .enums import RatingAgency

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RatingSubscriptions:
    """Подписки пользователя на агентства.

    ``stale`` означает, что бэкенд не ответил и подписки не известны: пустой
    набор здесь нельзя показывать как «вы ни на что не подписаны».
    """

    agencies: frozenset[RatingAgency]
    stale: bool = False


class RatingAlertSettingsRepository:
    """Доступ к подпискам пользователей на рейтинговые агентства."""

    @classmethod
    async def toggle(cls, telegram_id: int, agency: RatingAgency) -> bool:
        """Переключает подписку на агентство и возвращает новое состояние.

        Raises:
            BackendError: Бэкенд недоступен — хендлер покажет ошибку, а не
                соврёт пользователю про переключённое состояние.

        """
        return await api.toggle_agency(telegram_id, agency.value)

    @classmethod
    async def get(cls, telegram_id: int) -> RatingSubscriptions:
        """Подписки пользователя; при ошибке бэкенда — пустые с меткой ``stale``."""
        try:
            values = (await api.get_settings(telegram_id)).enabled_agencies
        except BackendError as e:
            logger.error(f"Ошибка при получении подписок пользователя {telegram_id}: {e}")
            return RatingSubscriptions(agencies=frozenset(), stale=True)

        enabled: set[RatingAgency] = set()
        for value in values:
            try:
                enabled.add(RatingAgency(value))
            except ValueError:
                # Бэкенд не знает про набор агентств — он хранит то, что ему прислали.
                logger.warning(f"Неизвестное агентство в подписках: {value}")
        return RatingSubscriptions(agencies=frozenset(enabled))

    @classmethod
    async def get_enabled_agencies(cls, telegram_id: int) -> set[RatingAgency]:
        """Возвращает множество агентств, на которые подписан пользователь."""
        return set((await cls.get(telegram_id)).agencies)
