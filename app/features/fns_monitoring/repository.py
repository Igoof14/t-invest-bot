"""CRUD подписок на блокировки ФНС и состояние дедупа блокировок."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from core.database import session_scope
from sqlalchemy import select

from .events import BlockingOrder
from .models import FnsAlertSettings, FnsBlockingRecord

logger = logging.getLogger(__name__)


class FnsAlertSettingsRepository:
    """Доступ к подпискам пользователей на уведомления о блокировках ФНС."""

    @classmethod
    async def toggle(cls, telegram_id: int) -> bool:
        """Переключает подписку пользователя и возвращает новое состояние."""
        async with session_scope() as session:
            result = await session.execute(
                select(FnsAlertSettings).where(
                    FnsAlertSettings.telegram_id == telegram_id
                )
            )
            settings = result.scalar_one_or_none()

            if settings is None:
                settings = FnsAlertSettings(telegram_id=telegram_id, alerts_enabled=True)
                session.add(settings)
            else:
                settings.alerts_enabled = not settings.alerts_enabled

            new_state = settings.alerts_enabled
            await session.commit()
            return new_state

    @classmethod
    async def is_enabled(cls, telegram_id: int) -> bool:
        """Возвращает, подписан ли пользователь на уведомления о блокировках."""
        try:
            async with session_scope() as session:
                result = await session.execute(
                    select(FnsAlertSettings.alerts_enabled).where(
                        FnsAlertSettings.telegram_id == telegram_id
                    )
                )
                return bool(result.scalar_one_or_none())
        except Exception as e:
            logger.error(f"Ошибка при получении подписки ФНС {telegram_id}: {e}")
            return False

    @classmethod
    async def list_users_with_alerts_enabled(cls) -> list[int]:
        """Возвращает telegram_id всех подписанных на уведомления пользователей."""
        try:
            async with session_scope() as session:
                result = await session.execute(
                    select(FnsAlertSettings.telegram_id).where(
                        FnsAlertSettings.alerts_enabled.is_(True)
                    )
                )
                return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Ошибка при получении подписчиков ФНС: {e}")
            return []


class FnsBlockingRepository:
    """Состояние дедупа решений о блокировке счетов (по ИНН)."""

    @classmethod
    async def has_any(cls, inn: str) -> bool:
        """Возвращает, проверялся ли ИНН ранее (есть ли записи в истории)."""
        try:
            async with session_scope() as session:
                result = await session.execute(
                    select(FnsBlockingRecord.id)
                    .where(FnsBlockingRecord.inn == inn)
                    .limit(1)
                )
                return result.scalar_one_or_none() is not None
        except Exception as e:
            logger.error(f"Ошибка при проверке истории блокировок ИНН {inn}: {e}")
            return False

    @classmethod
    async def sync(cls, inn: str, orders: list[BlockingOrder]) -> list[BlockingOrder]:
        """Синхронизирует текущие блокировки ИНН с БД.

        Создаёт новые записи, обновляет существующие и помечает исчезнувшие
        как ``resolved``.

        Args:
            inn: ИНН организации.
            orders: Текущие решения о блокировке из ответа ФНС.

        Returns:
            Подмножество ``orders`` — только впервые появившиеся блокировки
            (которые ранее не были активны).

        """
        new_orders: list[BlockingOrder] = []
        current_uids = {order.block_uid for order in orders}

        async with session_scope() as session:
            result = await session.execute(
                select(FnsBlockingRecord).where(FnsBlockingRecord.inn == inn)
            )
            existing = {rec.block_uid: rec for rec in result.scalars().all()}

            for order in orders:
                record = existing.get(order.block_uid)

                if record is None:
                    session.add(_to_record(order))
                    new_orders.append(order)
                    continue

                # Реактивация: блокировка снова появилась после снятия.
                if record.status == "resolved":
                    record.resolved_at = None
                    new_orders.append(order)
                record.status = "active"
                _update_record(record, order)

            # Активные записи, исчезнувшие из ответа, помечаем снятыми.
            for uid, record in existing.items():
                if uid not in current_uids and record.status == "active":
                    record.status = "resolved"
                    record.resolved_at = datetime.now(UTC)

            await session.commit()

        return new_orders


def _to_record(order: BlockingOrder) -> FnsBlockingRecord:
    """Создаёт новую ORM-запись из решения о блокировке."""
    return FnsBlockingRecord(
        inn=order.inn,
        block_uid=order.block_uid,
        bik=order.bik,
        nomer=order.nomer,
        decision_date=order.decision_date,
        date_begin=order.date_begin,
        kod_osnov=order.kod_osnov,
        saldo=order.saldo,
        ifns=order.ifns,
        entity_name=order.entity_name,
        status="active",
    )


def _update_record(record: FnsBlockingRecord, order: BlockingOrder) -> None:
    """Обновляет изменяемые поля существующей записи блокировки."""
    record.bik = order.bik
    record.nomer = order.nomer
    record.decision_date = order.decision_date
    record.date_begin = order.date_begin
    record.kod_osnov = order.kod_osnov
    record.saldo = order.saldo
    record.ifns = order.ifns
    record.entity_name = order.entity_name
