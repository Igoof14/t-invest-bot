import logging
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta, timezone

from core.database import session_scope
from sqlalchemy import delete, func, select, update

from .models import PriceAlertSettings
from .schemas import BondPrice

logger = logging.getLogger(__name__)


# Часовой пояс Москвы (для подсчёта "сегодня" по местному времени)
MOSCOW_TZ = timezone(timedelta(hours=3))


class AlertSettingsRepository:
    """Доступ к настройкам уведомлений о ценах для пользователя."""

    @classmethod
    async def get(cls, telegram_id: int) -> PriceAlertSettings | None:
        """Возвращает настройки пользователя или None, если их нет."""
        try:
            async with session_scope() as session:
                result = await session.execute(
                    select(PriceAlertSettings).where(PriceAlertSettings.telegram_id == telegram_id)
                )
                settings = result.scalar_one_or_none()
                if settings is not None:
                    session.expunge(settings)
                return settings
        except Exception as e:
            logger.error(f"Ошибка при получении настроек пользователя {telegram_id}: {e}")
            return None

    @classmethod
    async def get_or_create(cls, telegram_id: int) -> PriceAlertSettings:
        """Возвращает настройки пользователя, создавая их при отсутствии."""
        async with session_scope() as session:
            result = await session.execute(
                select(PriceAlertSettings).where(PriceAlertSettings.telegram_id == telegram_id)
            )
            settings = result.scalar_one_or_none()

            if settings is None:
                settings = PriceAlertSettings(telegram_id=telegram_id)
                session.add(settings)
                await session.commit()
                await session.refresh(settings)
                logger.info(f"Созданы настройки уведомлений для пользователя {telegram_id}")

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
                    update(PriceAlertSettings)
                    .where(PriceAlertSettings.telegram_id == telegram_id)
                    .values(**fields)
                )
                await session.commit()

                affected = getattr(result, "rowcount", 0)
                if affected > 0:
                    logger.info(f"Обновлены настройки уведомлений пользователя {telegram_id}")
                    return True
                return False
        except Exception as e:
            logger.error(f"Ошибка при обновлении настроек пользователя {telegram_id}: {e}")
            return False

    @classmethod
    async def toggle_alerts(cls, telegram_id: int) -> bool:
        """Переключает флаг alerts_enabled и возвращает новое значение."""
        settings = await cls.get_or_create(telegram_id)
        new_state = not settings.alerts_enabled
        await cls.update(telegram_id, alerts_enabled=new_state)
        return new_state

    @classmethod
    async def list_users_with_alerts_enabled(cls) -> list[PriceAlertSettings]:
        """Возвращает настройки всех пользователей с включёнными алертами."""
        try:
            async with session_scope() as session:
                result = await session.execute(
                    select(PriceAlertSettings).where(PriceAlertSettings.alerts_enabled.is_(True))
                )
                rows = list(result.scalars().all())
                for row in rows:
                    session.expunge(row)
                return rows
        except Exception as e:
            logger.error(f"Ошибка при получении пользователей с уведомлениями: {e}")
            return []

