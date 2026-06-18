"""CRUD подписок на уведомления о купонах и трекинга ожидаемых купонов."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, time

from core.database import session_scope
from sqlalchemy import select

from .models import NsdCouponAlertSettings, NsdCouponTracking
from .schemas import CouponPlan

logger = logging.getLogger(__name__)


class NsdCouponAlertSettingsRepository:
    """Доступ к подпискам пользователей на уведомления о купонах."""

    @classmethod
    async def toggle(cls, telegram_id: int) -> bool:
        """Переключает подписку пользователя и возвращает новое состояние."""
        async with session_scope() as session:
            result = await session.execute(
                select(NsdCouponAlertSettings).where(
                    NsdCouponAlertSettings.telegram_id == telegram_id
                )
            )
            settings = result.scalar_one_or_none()

            if settings is None:
                settings = NsdCouponAlertSettings(
                    telegram_id=telegram_id, alerts_enabled=True
                )
                session.add(settings)
            else:
                settings.alerts_enabled = not settings.alerts_enabled

            new_state = settings.alerts_enabled
            await session.commit()
            return new_state

    @classmethod
    async def is_enabled(cls, telegram_id: int) -> bool:
        """Возвращает, подписан ли пользователь на уведомления о купонах."""
        try:
            async with session_scope() as session:
                result = await session.execute(
                    select(NsdCouponAlertSettings.alerts_enabled).where(
                        NsdCouponAlertSettings.telegram_id == telegram_id
                    )
                )
                return bool(result.scalar_one_or_none())
        except Exception as e:
            logger.error(f"Ошибка при получении подписки на купоны {telegram_id}: {e}")
            return False

    @classmethod
    async def list_users_with_alerts_enabled(cls) -> list[int]:
        """Возвращает telegram_id всех подписанных на уведомления пользователей."""
        try:
            async with session_scope() as session:
                result = await session.execute(
                    select(NsdCouponAlertSettings.telegram_id).where(
                        NsdCouponAlertSettings.alerts_enabled.is_(True)
                    )
                )
                return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Ошибка при получении подписчиков на купоны: {e}")
            return []

    @classmethod
    async def set_report_time(cls, telegram_id: int, value: time | None) -> None:
        """Задаёт время ежедневного отчёта (``None`` — выключить отчёт)."""
        async with session_scope() as session:
            result = await session.execute(
                select(NsdCouponAlertSettings).where(
                    NsdCouponAlertSettings.telegram_id == telegram_id
                )
            )
            settings = result.scalar_one_or_none()
            if settings is None:
                settings = NsdCouponAlertSettings(telegram_id=telegram_id)
                session.add(settings)
            settings.report_time = value
            await session.commit()

    @classmethod
    async def get_report_time(cls, telegram_id: int) -> time | None:
        """Возвращает время ежедневного отчёта пользователя или ``None``."""
        try:
            async with session_scope() as session:
                result = await session.execute(
                    select(NsdCouponAlertSettings.report_time).where(
                        NsdCouponAlertSettings.telegram_id == telegram_id
                    )
                )
                return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Ошибка при получении времени отчёта {telegram_id}: {e}")
            return None

    @classmethod
    async def list_users_with_report_at(cls, hour: int, minute: int) -> list[int]:
        """Возвращает telegram_id пользователей с временем отчёта = ``hour:minute``."""
        try:
            async with session_scope() as session:
                result = await session.execute(
                    select(NsdCouponAlertSettings.telegram_id).where(
                        NsdCouponAlertSettings.report_time == time(hour, minute)
                    )
                )
                return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Ошибка при выборке отчётов на {hour}:{minute}: {e}")
            return []


class NsdCouponTrackingRepository:
    """Состояние трекинга ожидаемых купонов (по паре isin + coupon_number)."""

    @classmethod
    async def upsert_pending(cls, plans: list[CouponPlan]) -> int:
        """Добавляет новые ожидаемые купоны, пропуская уже отслеживаемые.

        Args:
            plans: Плановые купоны из календаря T-Invest.

        Returns:
            Число добавленных записей.

        """
        if not plans:
            return 0

        added = 0
        async with session_scope() as session:
            # Одним запросом тянем уже отслеживаемые пары (isin, coupon_number)
            # по затронутым ISIN (фильтр по индексированному столбцу), чтобы
            # не делать SELECT на каждый купон.
            isins = {plan.isin for plan in plans}
            result = await session.execute(
                select(
                    NsdCouponTracking.isin, NsdCouponTracking.coupon_number
                ).where(NsdCouponTracking.isin.in_(isins))
            )
            known: set[tuple[str, int]] = {
                (isin, number) for isin, number in result.all()
            }

            for plan in plans:
                key = (plan.isin, plan.coupon_number)
                if key in known:
                    continue
                # Учитываем дубликаты внутри самого батча.
                known.add(key)
                session.add(
                    NsdCouponTracking(
                        isin=plan.isin,
                        figi=plan.figi,
                        coupon_number=plan.coupon_number,
                        coupon_date=plan.coupon_date,
                        amount=plan.amount,
                        bond_name=plan.bond_name,
                        issuer_name=plan.issuer_name,
                        status="pending",
                    )
                )
                added += 1
            await session.commit()
        return added

    @classmethod
    async def list_pending_due(cls, as_of: date) -> list[NsdCouponTracking]:
        """Возвращает ожидаемые купоны с плановой датой не позже ``as_of``.

        Используется и для проверки публикаций НРД, и для дедлайн-проверки.
        Объекты отсоединены от сессии (можно читать атрибуты вне неё).

        Args:
            as_of: Верхняя граница плановой даты купона (включительно).

        Returns:
            Список ожидаемых купонов в статусе ``pending``.

        """
        async with session_scope() as session:
            result = await session.execute(
                select(NsdCouponTracking).where(
                    NsdCouponTracking.status == "pending",
                    NsdCouponTracking.coupon_date <= as_of,
                )
            )
            records = list(result.scalars().all())
            for record in records:
                session.expunge(record)
            return records

    @classmethod
    async def mark_paid(
        cls, coupon_id: int, news_id: int | None, received_at: datetime | None = None
    ) -> None:
        """Помечает купон выплаченным (НРД опубликовал выплату)."""
        async with session_scope() as session:
            record = await session.get(NsdCouponTracking, coupon_id)
            if record is None:
                return
            record.status = "paid"
            record.nsd_news_id = news_id
            record.paid_at = received_at or datetime.now(UTC)
            await session.commit()

    @classmethod
    async def mark_alerted(cls, coupon_id: int) -> None:
        """Помечает купон как просроченный с разосланным уведомлением."""
        async with session_scope() as session:
            record = await session.get(NsdCouponTracking, coupon_id)
            if record is None:
                return
            record.status = "alerted"
            record.alerted_at = datetime.now(UTC)
            await session.commit()
