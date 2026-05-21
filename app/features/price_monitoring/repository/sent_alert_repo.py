"""Репозиторий отправленных алертов (anti-spam учёт)."""

import logging
from datetime import UTC, datetime, timedelta, timezone

from core.database import session_scope
from sqlalchemy import delete, func, select

from ..models import PriceAlertSent

logger = logging.getLogger(__name__)

# Часовой пояс Москвы (для подсчёта "сегодня" по местному времени)
MOSCOW_TZ = timezone(timedelta(hours=3))


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
