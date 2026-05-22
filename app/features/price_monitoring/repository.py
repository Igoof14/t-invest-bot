import logging
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta, timezone

from core.database import session_scope
from sqlalchemy import delete, func, select, update

from .models import BondPriceHistory, PriceAlertSent, PriceAlertSettings
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


class SentAlertRepository:
    """Доступ к таблице отправленных алертов."""

    @classmethod
    async def record(cls, telegram_id: int, figi: str, alert_type: str) -> bool:
        """Записывает факт отправки алерта."""
        try:
            async with session_scope() as session:
                session.add(
                    PriceAlertSent(
                        telegram_id=telegram_id,
                        figi=figi,
                        alert_type=alert_type,
                    )
                )
                await session.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка при записи алерта: {e}")
            return False

    @classmethod
    async def has_recent(cls, telegram_id: int, figi: str, *, hours: int) -> bool:
        """Проверяет, был ли алерт по бумаге за последние ``hours`` часов."""
        try:
            async with session_scope() as session:
                cooldown_time = datetime.now(UTC) - timedelta(hours=hours)
                result = await session.execute(
                    select(PriceAlertSent.id)
                    .where(
                        PriceAlertSent.telegram_id == telegram_id,
                        PriceAlertSent.figi == figi,
                        PriceAlertSent.sent_at > cooldown_time,
                    )
                    .limit(1)
                )
                return result.scalar_one_or_none() is not None
        except Exception as e:
            logger.error(f"Ошибка при проверке cooldown: {e}")
            # В случае ошибки разрешаем отправку — лучше лишний алерт, чем тишина
            return False

    @classmethod
    async def count_today(cls, telegram_id: int) -> int:
        """Количество отправленных алертов за сегодня (по московскому времени)."""
        try:
            async with session_scope() as session:
                now_moscow = datetime.now(MOSCOW_TZ)
                today_start = now_moscow.replace(
                    hour=0, minute=0, second=0, microsecond=0
                ).astimezone(UTC)
                result = await session.execute(
                    select(func.count(PriceAlertSent.id)).where(
                        PriceAlertSent.telegram_id == telegram_id,
                        PriceAlertSent.sent_at >= today_start,
                    )
                )
                return result.scalar() or 0
        except Exception as e:
            logger.error(f"Ошибка при подсчёте дневных алертов: {e}")
            return 0

    @classmethod
    async def last_alert_type(cls, telegram_id: int, figi: str) -> str | None:
        """Возвращает тип последнего отправленного алерта по бумаге."""
        try:
            async with session_scope() as session:
                result = await session.execute(
                    select(PriceAlertSent.alert_type)
                    .where(
                        PriceAlertSent.telegram_id == telegram_id,
                        PriceAlertSent.figi == figi,
                    )
                    .order_by(PriceAlertSent.sent_at.desc())
                    .limit(1)
                )
                return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Ошибка при получении последнего алерта: {e}")
            return None

    @classmethod
    async def cleanup_older_than(cls, days_to_keep: int = 7) -> int:
        """Удаляет записи алертов старше указанного количества дней."""
        try:
            async with session_scope() as session:
                cutoff_date = datetime.now(UTC) - timedelta(days=days_to_keep)
                result = await session.execute(
                    delete(PriceAlertSent).where(PriceAlertSent.sent_at < cutoff_date)
                )
                await session.commit()
                deleted = getattr(result, "rowcount", 0)
                logger.info(f"Удалено {deleted} старых алертов")
                return deleted
        except Exception as e:
            logger.error(f"Ошибка при очистке старых алертов: {e}")
            return 0


class PriceHistoryRepository:
    """Доступ к таблице снимков цен облигаций."""

    @classmethod
    async def get_latest(cls, telegram_id: int) -> list[BondPrice]:
        """Возвращает последний снимок цен по каждой облигации пользователя."""
        try:
            async with session_scope() as session:
                # Подзапрос: последнее время записи для каждого figi
                latest_per_figi = (
                    select(
                        BondPriceHistory.figi,
                        func.max(BondPriceHistory.recorded_at).label("max_recorded"),
                    )
                    .where(BondPriceHistory.telegram_id == telegram_id)
                    .group_by(BondPriceHistory.figi)
                    .subquery()
                )

                result = await session.execute(
                    select(BondPriceHistory)
                    .join(
                        latest_per_figi,
                        (BondPriceHistory.figi == latest_per_figi.c.figi)
                        & (BondPriceHistory.recorded_at == latest_per_figi.c.max_recorded),
                    )
                    .where(BondPriceHistory.telegram_id == telegram_id)
                    # Стабильный порядок: при наличии старых дублей (один FIGI из нескольких
                    # счетов с одинаковым recorded_at) Python-дедупликация возьмёт строку
                    # с наименьшим id, а не случайную.
                    .order_by(BondPriceHistory.figi, BondPriceHistory.id)
                )

                rows = result.scalars().all()
                return [
                    BondPrice(
                        figi=row.figi,
                        ticker=row.ticker,
                        name=row.name,
                        price=row.price,
                        account_name=row.account_name or "",
                    )
                    for row in rows
                ]

        except Exception as e:
            logger.error(f"Ошибка при получении цен пользователя {telegram_id}: {e}")
            return []

    @classmethod
    async def save_snapshot(cls, telegram_id: int, prices: Iterable[BondPrice]) -> bool:
        """Сохраняет снимок текущих цен для пользователя."""
        prices_list = list(prices)
        try:
            async with session_scope() as session:
                for price in prices_list:
                    session.add(
                        BondPriceHistory(
                            telegram_id=telegram_id,
                            figi=price.figi,
                            ticker=price.ticker,
                            name=price.name,
                            price=price.price,
                            account_name=price.account_name,
                        )
                    )
                await session.commit()
                logger.debug(f"Сохранено {len(prices_list)} цен для пользователя {telegram_id}")
                return True
        except Exception as e:
            logger.error(f"Ошибка при сохранении цен пользователя {telegram_id}: {e}")
            return False

    @classmethod
    async def cleanup_older_than(cls, days_to_keep: int = 7) -> int:
        """Удаляет записи цен старше указанного количества дней."""
        try:
            async with session_scope() as session:
                cutoff_date = datetime.now(UTC) - timedelta(days=days_to_keep)
                result = await session.execute(
                    delete(BondPriceHistory).where(BondPriceHistory.recorded_at < cutoff_date)
                )
                await session.commit()
                deleted = getattr(result, "rowcount", 0)
                logger.info(f"Удалено {deleted} старых записей цен")
                return deleted
        except Exception as e:
            logger.error(f"Ошибка при очистке старых цен: {e}")
            return 0
