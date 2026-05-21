"""Репозиторий истории цен облигаций."""

import logging
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from core.clients.t_invest.portfolio_prices import BondPrice
from core.database import session_scope
from sqlalchemy import delete, func, select

from ..models import BondPriceHistory

logger = logging.getLogger(__name__)


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
