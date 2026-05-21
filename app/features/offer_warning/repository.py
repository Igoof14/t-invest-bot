"""CRUD для уведомлений об офертах."""

import logging

from core.database import session_scope
from sqlalchemy import select, update

from .models import OfferAlertSettings

logger = logging.getLogger(__name__)


class OfferSettingsRepository:
    """Доступ к настройкам уведомлений о ценах для пользователя."""

    @classmethod
    async def get(cls, telegram_id: int) -> OfferAlertSettings | None:
        """Возвращает настройки пользователя или None, если их нет."""
        try:
            async with session_scope() as session:
                result = await session.execute(
                    select(OfferAlertSettings).where(OfferAlertSettings.telegram_id == telegram_id)
                )
                settings = result.scalar_one_or_none()
                if settings is not None:
                    session.expunge(settings)
                return settings
        except Exception as e:
            logger.error(f"Ошибка при получении настроек о офертах пользователя {telegram_id}: {e}")
            return None

    @classmethod
    async def get_or_create(cls, telegram_id: int) -> OfferAlertSettings:
        """Возвращает настройки пользователя, создавая их при отсутствии."""
        async with session_scope() as session:
            result = await session.execute(
                select(OfferAlertSettings).where(OfferAlertSettings.telegram_id == telegram_id)
            )
            settings = result.scalar_one_or_none()

            if settings is None:
                settings = OfferAlertSettings(telegram_id=telegram_id)
                session.add(settings)
                await session.commit()
                await session.refresh(settings)
                logger.info(
                    f"Созданы настройки уведомлений о офертах для пользователя {telegram_id}"
                )

            session.expunge(settings)
            return settings

    @classmethod
    async def update(cls, telegram_id: int, **fields: object) -> bool:
        """Обновляет поля настроек пользователя.

        Если настроек ещё нет, они создаются с дефолтными значениями
        и затем сразу обновляются.
        """
        # Убеждаемся, что запись существует
        await cls.get_or_create(telegram_id)

        try:
            async with session_scope() as session:
                result = await session.execute(
                    update(OfferAlertSettings)
                    .where(OfferAlertSettings.telegram_id == telegram_id)
                    .values(**fields)
                )
                await session.commit()

                affected = getattr(result, "rowcount", 0)
                if affected > 0:
                    logger.info(
                        f"Обновлены настройки уведомлений о офертах пользователя {telegram_id}"
                    )
                    return True
                return False
        except Exception as e:
            logger.error(
                f"Ошибка при обновлении настроек о офертах пользователя {telegram_id}: {e}"
            )
            return False

    @classmethod
    async def toggle_alerts(cls, telegram_id: int) -> bool:
        """Переключает флаг alerts_enabled и возвращает новое значение."""
        settings = await cls.get_or_create(telegram_id)
        new_state = not settings.alerts_enabled
        await cls.update(telegram_id, alerts_enabled=new_state)
        return new_state

    @classmethod
    async def list_users_with_alerts_enabled(cls) -> list[int]:
        """Возвращает telegram_id всех пользователей, у которых включены алерты."""
        try:
            async with session_scope() as session:
                result = await session.execute(
                    select(OfferAlertSettings.telegram_id).where(
                        OfferAlertSettings.alerts_enabled.is_(True)
                    )
                )
                return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Ошибка при получении пользователей с уведомлениями: {e}")
            return []
