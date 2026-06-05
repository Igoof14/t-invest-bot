"""Базовый оркестратор полинга рейтингов (общий для провайдеров)."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from aiogram import Bot

from .enums import RatingAgency
from .events import ChangeType, RatingEvent
from .notifier import RatingAlertNotifier
from .pipeline import notify_subscribers, resolve_events
from .repository import RatingReleaseRepository

logger = logging.getLogger(__name__)


class BaseRatingAlertService(ABC):
    """Общий конвейер: опрос → дедуп → прогрев → резолв → рассылка.

    Провайдер задаёт ``agency`` и реализует ``_poll`` (свой клиент/парсер).
    """

    agency: RatingAgency

    def __init__(self, bot: Bot, *, notifier: RatingAlertNotifier | None = None) -> None:
        """Собирает сервис."""
        self._bot = bot
        self._notifier = notifier or RatingAlertNotifier(bot)

    @classmethod
    async def check_rating_updates(cls, bot: Bot) -> None:
        """Точка входа scheduler-джоба."""
        await cls(bot).run_check()

    async def run_check(self) -> None:
        """Опрашивает агентство и рассылает уведомления по изменениям."""
        agency = self.agency.value
        logger.info(f"Запуск проверки обновлений рейтингов {agency}")

        known = await RatingReleaseRepository.get_seen(self.agency)
        is_first_run = not known

        events, change_by_uid = await self._poll(known)
        await RatingReleaseRepository.upsert_many(self.agency, events)

        if is_first_run:
            logger.info(
                f"Первый запуск {agency}: сохранено {len(events)} релизов, "
                "уведомления не отправляются"
            )
            return

        if not events:
            logger.info(f"Новых изменений рейтингов {agency} нет")
            return

        resolved = await resolve_events(events, change_by_uid)
        if not resolved:
            logger.info(f"Изменения {agency} не относятся к эмитентам из реестра")
            return

        await notify_subscribers(self._bot, self.agency, resolved, self._notifier)
        logger.info(f"Проверка обновлений рейтингов {agency} завершена")

    @abstractmethod
    async def _poll(
        self, known: dict[str, str | None]
    ) -> tuple[list[RatingEvent], dict[str, ChangeType]]:
        """Опрашивает источник и возвращает новые/изменённые события + их тип."""
        raise NotImplementedError
