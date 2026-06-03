"""CRUD подписок на уведомления о рейтингах."""

from __future__ import annotations

import logging

from core.database import session_scope
from sqlalchemy import select

from .enums import RatingAgency
from .models import RatingAlertSettings

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
