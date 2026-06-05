"""CRUD подписок на уведомления о рейтингах."""

from __future__ import annotations

import logging

from core.database import session_scope
from sqlalchemy import select

from .enums import RatingAgency
from .events import ChangeType, RatingEvent
from .models import RatingAlertSettings, RatingRelease

logger = logging.getLogger(__name__)


class RatingAlertSettingsRepository:
    """Доступ к подпискам пользователей на рейтинговые агентства."""

    @classmethod
    async def get_or_create(
        cls, telegram_id: int, agency: RatingAgency
    ) -> RatingAlertSettings:
        """Возвращает подписку пользователя на агентство, создавая при отсутствии."""
        async with session_scope() as session:
            result = await session.execute(
                select(RatingAlertSettings).where(
                    RatingAlertSettings.telegram_id == telegram_id,
                    RatingAlertSettings.agency == agency.value,
                )
            )
            settings = result.scalar_one_or_none()

            if settings is None:
                settings = RatingAlertSettings(telegram_id=telegram_id, agency=agency.value)
                session.add(settings)
                await session.commit()
                await session.refresh(settings)
                logger.info(
                    f"Создана подписка на рейтинги {agency.value} "
                    f"для пользователя {telegram_id}"
                )

            session.expunge(settings)
            return settings

    @classmethod
    async def toggle(cls, telegram_id: int, agency: RatingAgency) -> bool:
        """Переключает подписку на агентство и возвращает новое состояние."""
        async with session_scope() as session:
            result = await session.execute(
                select(RatingAlertSettings).where(
                    RatingAlertSettings.telegram_id == telegram_id,
                    RatingAlertSettings.agency == agency.value,
                )
            )
            settings = result.scalar_one_or_none()

            if settings is None:
                settings = RatingAlertSettings(
                    telegram_id=telegram_id, agency=agency.value, alerts_enabled=True
                )
                session.add(settings)
            else:
                settings.alerts_enabled = not settings.alerts_enabled

            new_state = settings.alerts_enabled
            await session.commit()
            return new_state

    @classmethod
    async def get_enabled_agencies(cls, telegram_id: int) -> set[RatingAgency]:
        """Возвращает множество агентств, на которые подписан пользователь."""
        try:
            async with session_scope() as session:
                result = await session.execute(
                    select(RatingAlertSettings.agency).where(
                        RatingAlertSettings.telegram_id == telegram_id,
                        RatingAlertSettings.alerts_enabled.is_(True),
                    )
                )
                values = result.scalars().all()
        except Exception as e:
            logger.error(f"Ошибка при получении подписок пользователя {telegram_id}: {e}")
            return set()

        enabled: set[RatingAgency] = set()
        for value in values:
            try:
                enabled.add(RatingAgency(value))
            except ValueError:
                logger.warning(f"Неизвестное агентство в подписках: {value}")
        return enabled

    @classmethod
    async def list_users_with_alerts_enabled(cls, agency: RatingAgency) -> list[int]:
        """Возвращает telegram_id всех подписанных на агентство пользователей."""
        try:
            async with session_scope() as session:
                result = await session.execute(
                    select(RatingAlertSettings.telegram_id).where(
                        RatingAlertSettings.agency == agency.value,
                        RatingAlertSettings.alerts_enabled.is_(True),
                    )
                )
                return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Ошибка при получении подписчиков {agency.value}: {e}")
            return []


class RatingReleaseRepository:
    """Состояние дедупа увиденных релизов (общая таблица на провайдеров)."""

    @classmethod
    async def get_seen(cls, agency: RatingAgency) -> dict[str, str | None]:
        """Возвращает снимок ``{uid: modified}`` увиденных релизов агентства."""
        try:
            async with session_scope() as session:
                result = await session.execute(
                    select(RatingRelease.uid, RatingRelease.modified).where(
                        RatingRelease.agency == agency.value
                    )
                )
                return {uid: modified for uid, modified in result.all()}
        except Exception as e:
            logger.error(f"Ошибка при получении снимка релизов {agency.value}: {e}")
            return {}

    @classmethod
    async def upsert_many(cls, agency: RatingAgency, events: list[RatingEvent]) -> None:
        """Создаёт или обновляет релизы агентства по ``uid``."""
        if not events:
            return

        async with session_scope() as session:
            for event in events:
                result = await session.execute(
                    select(RatingRelease).where(
                        RatingRelease.agency == agency.value,
                        RatingRelease.uid == event.uid,
                    )
                )
                release = result.scalar_one_or_none()

                if release is None:
                    release = RatingRelease(agency=agency.value, uid=event.uid)
                    session.add(release)

                release.url = event.url
                release.release_id = event.release_id
                release.inn = event.inn
                release.isins = ", ".join(event.isins) if event.isins else None
                release.entity_name = event.entity_name
                release.entity_type = event.entity_type
                release.rating_action = event.rating_action
                release.rating_value = event.rating_value
                release.outlook = event.outlook
                release.publication_date = event.publication_date
                release.modified = event.modified.isoformat() if event.modified else None

            await session.commit()

    @staticmethod
    def classify(
        uid: str, modified_iso: str | None, known: dict[str, str | None]
    ) -> ChangeType | None:
        """Классифицирует релиз: NEW (неизвестен), CHANGED (modified новее), иначе None."""
        if uid not in known:
            return ChangeType.NEW
        if modified_iso is not None and modified_iso != known[uid]:
            return ChangeType.CHANGED
        return None
