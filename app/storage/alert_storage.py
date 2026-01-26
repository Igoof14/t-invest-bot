"""Модуль для управления данными уведомлений о ценах."""

import logging
from datetime import datetime, timedelta

from core.database import get_session
from models.alerts import BondPriceHistory, SentAlert, UserAlertSettings
from sqlalchemy import delete, func, select, update

logger = logging.getLogger(__name__)

# Константы
ALERT_COOLDOWN_HOURS = 4
MAX_DAILY_ALERTS = 10


class AlertStorage:
    """Класс для управления данными уведомлений."""

    # === Настройки пользователя ===

    @classmethod
    async def get_user_settings(cls, telegram_id: int) -> UserAlertSettings | None:
        """Получает настройки уведомлений пользователя."""
        async for session in get_session():
            try:
                result = await session.execute(
                    select(UserAlertSettings).where(UserAlertSettings.telegram_id == telegram_id)
                )
                return result.scalar_one_or_none()
            except Exception as e:
                logger.error(f"Ошибка при получении настроек пользователя {telegram_id}: {e}")
                return None
        return None

    @classmethod
    async def get_or_create_user_settings(cls, telegram_id: int) -> UserAlertSettings:
        """Получает или создаёт настройки уведомлений пользователя."""
        async for session in get_session():
            try:
                result = await session.execute(
                    select(UserAlertSettings).where(UserAlertSettings.telegram_id == telegram_id)
                )
                settings = result.scalar_one_or_none()

                if settings:
                    return settings

                # Создаём новые настройки с дефолтными значениями
                settings = UserAlertSettings(telegram_id=telegram_id)
                session.add(settings)
                await session.commit()
                await session.refresh(settings)

                logger.info(f"Созданы настройки уведомлений для пользователя {telegram_id}")
                return settings

            except Exception as e:
                await session.rollback()
                logger.error(f"Ошибка при создании настроек пользователя {telegram_id}: {e}")
                raise e
        raise RuntimeError("Не удалось получить сессию БД")

    @classmethod
    async def update_user_settings(cls, telegram_id: int, **kwargs) -> bool:
        """Обновляет настройки уведомлений пользователя."""
        async for session in get_session():
            try:
                # Сначала убедимся, что настройки существуют
                await cls.get_or_create_user_settings(telegram_id)

                result = await session.execute(
                    update(UserAlertSettings)
                    .where(UserAlertSettings.telegram_id == telegram_id)
                    .values(**kwargs)
                )
                await session.commit()

                affected = getattr(result, "rowcount", 0)
                if affected > 0:
                    logger.info(f"Обновлены настройки уведомлений пользователя {telegram_id}")
                    return True
                return False

            except Exception as e:
                await session.rollback()
                logger.error(f"Ошибка при обновлении настроек пользователя {telegram_id}: {e}")
                return False
        return False

    @classmethod
    async def toggle_alerts(cls, telegram_id: int) -> bool:
        """Переключает состояние уведомлений. Возвращает новое состояние."""
        settings = await cls.get_or_create_user_settings(telegram_id)
        new_state = not settings.alerts_enabled
        await cls.update_user_settings(telegram_id, alerts_enabled=new_state)
        return new_state

    @classmethod
    async def get_all_users_with_alerts_enabled(cls) -> list[int]:
        """Возвращает список telegram_id пользователей с включенными уведомлениями."""
        async for session in get_session():
            try:
                result = await session.execute(
                    select(UserAlertSettings.telegram_id).where(
                        UserAlertSettings.alerts_enabled == True  # noqa: E712
                    )
                )
                return list(result.scalars().all())
            except Exception as e:
                logger.error(f"Ошибка при получении пользователей с уведомлениями: {e}")
                return []
        return []

    # === История цен ===

    @classmethod
    async def get_latest_prices(cls, telegram_id: int) -> list[BondPriceHistory]:
        """Получает последние сохранённые цены облигаций пользователя."""
        async for session in get_session():
            try:
                # Получаем последнюю запись для каждой облигации
                subquery = (
                    select(
                        BondPriceHistory.figi,
                        func.max(BondPriceHistory.recorded_at).label("max_recorded")
                    )
                    .where(BondPriceHistory.telegram_id == telegram_id)
                    .group_by(BondPriceHistory.figi)
                    .subquery()
                )

                result = await session.execute(
                    select(BondPriceHistory)
                    .join(
                        subquery,
                        (BondPriceHistory.figi == subquery.c.figi)
                        & (BondPriceHistory.recorded_at == subquery.c.max_recorded)
                    )
                    .where(BondPriceHistory.telegram_id == telegram_id)
                )

                return list(result.scalars().all())

            except Exception as e:
                logger.error(f"Ошибка при получении цен пользователя {telegram_id}: {e}")
                return []
        return []

    @classmethod
    async def save_price_snapshot(
        cls, telegram_id: int, prices: list[dict]
    ) -> bool:
        """Сохраняет текущие цены облигаций.

        Args:
            telegram_id: ID пользователя
            prices: Список словарей с ключами: figi, ticker, name, price_percent, account_name

        Returns:
            True если успешно, False иначе

        """
        async for session in get_session():
            try:
                for price_data in prices:
                    record = BondPriceHistory(
                        telegram_id=telegram_id,
                        figi=price_data["figi"],
                        ticker=price_data["ticker"],
                        name=price_data["name"],
                        price_percent=price_data["price_percent"],
                        account_name=price_data.get("account_name"),
                    )
                    session.add(record)

                await session.commit()
                logger.debug(f"Сохранено {len(prices)} цен для пользователя {telegram_id}")
                return True

            except Exception as e:
                await session.rollback()
                logger.error(f"Ошибка при сохранении цен пользователя {telegram_id}: {e}")
                return False
        return False

    @classmethod
    async def cleanup_old_prices(cls, days_to_keep: int = 7) -> int:
        """Удаляет старые записи цен."""
        async for session in get_session():
            try:
                cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
                result = await session.execute(
                    delete(BondPriceHistory).where(BondPriceHistory.recorded_at < cutoff_date)
                )
                await session.commit()
                deleted = getattr(result, "rowcount", 0)
                logger.info(f"Удалено {deleted} старых записей цен")
                return deleted
            except Exception as e:
                await session.rollback()
                logger.error(f"Ошибка при очистке старых цен: {e}")
                return 0
        return 0

    # === Anti-spam механизмы ===

    @classmethod
    async def record_sent_alert(cls, telegram_id: int, figi: str, alert_type: str) -> bool:
        """Записывает отправленный алерт."""
        async for session in get_session():
            try:
                record = SentAlert(
                    telegram_id=telegram_id,
                    figi=figi,
                    alert_type=alert_type,
                )
                session.add(record)
                await session.commit()
                return True
            except Exception as e:
                await session.rollback()
                logger.error(f"Ошибка при записи алерта: {e}")
                return False
        return False

    @classmethod
    async def can_send_alert(cls, telegram_id: int, figi: str) -> bool:
        """Проверяет, можно ли отправить алерт (cooldown 4 часа)."""
        async for session in get_session():
            try:
                cooldown_time = datetime.utcnow() - timedelta(hours=ALERT_COOLDOWN_HOURS)
                result = await session.execute(
                    select(SentAlert)
                    .where(
                        SentAlert.telegram_id == telegram_id,
                        SentAlert.figi == figi,
                        SentAlert.sent_at > cooldown_time,
                    )
                    .limit(1)
                )
                recent_alert = result.scalar_one_or_none()
                return recent_alert is None
            except Exception as e:
                logger.error(f"Ошибка при проверке cooldown: {e}")
                return True  # В случае ошибки разрешаем отправку
        return True

    @classmethod
    async def get_daily_alert_count(cls, telegram_id: int) -> int:
        """Возвращает количество алертов за сегодня."""
        async for session in get_session():
            try:
                today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                result = await session.execute(
                    select(func.count(SentAlert.id)).where(
                        SentAlert.telegram_id == telegram_id,
                        SentAlert.sent_at >= today_start,
                    )
                )
                return result.scalar() or 0
            except Exception as e:
                logger.error(f"Ошибка при подсчёте дневных алертов: {e}")
                return 0
        return 0

    @classmethod
    async def can_send_more_alerts_today(cls, telegram_id: int) -> bool:
        """Проверяет, не превышен ли дневной лимит алертов."""
        count = await cls.get_daily_alert_count(telegram_id)
        return count < MAX_DAILY_ALERTS

    @classmethod
    async def get_last_alert_type(cls, telegram_id: int, figi: str) -> str | None:
        """Возвращает тип последнего алерта для данной облигации."""
        async for session in get_session():
            try:
                result = await session.execute(
                    select(SentAlert.alert_type)
                    .where(
                        SentAlert.telegram_id == telegram_id,
                        SentAlert.figi == figi,
                    )
                    .order_by(SentAlert.sent_at.desc())
                    .limit(1)
                )
                return result.scalar_one_or_none()
            except Exception as e:
                logger.error(f"Ошибка при получении последнего алерта: {e}")
                return None
        return None

    @classmethod
    async def cleanup_old_alerts(cls, days_to_keep: int = 7) -> int:
        """Удаляет старые записи алертов."""
        async for session in get_session():
            try:
                cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
                result = await session.execute(
                    delete(SentAlert).where(SentAlert.sent_at < cutoff_date)
                )
                await session.commit()
                deleted = getattr(result, "rowcount", 0)
                logger.info(f"Удалено {deleted} старых алертов")
                return deleted
            except Exception as e:
                await session.rollback()
                logger.error(f"Ошибка при очистке старых алертов: {e}")
                return 0
        return 0
