"""Настройка подключения к базе данных."""

import logging
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from core.config import config

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""

    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class DatabaseManager:
    """Менеджер базы данных."""

    def __init__(self, database_url: str):
        """Инициализирует менеджер базы данных."""
        self.engine = create_async_engine(
            database_url,
            echo=False,
            future=True,
            pool_size=5,
            max_overflow=10,
        )
        self.session_factory = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def create_tables(self) -> None:
        """Создает все таблицы в базе данных."""
        try:
            # Укажите здесь актуальные пути в зависимости от вашей структуры.
            # Если перешли на Feature-driven, пути будут такими:
            from features.fns_monitoring.models import (
                FnsAlertSettings,
                FnsBlockingRecord,
            )
            from features.issuers.models import Issuer, IssuerBond
            from features.offer_warning.models import OfferAlertSettings
            from features.price_monitoring.models import (
                BondLastPrice,
                BondPriceHistory,
                PriceAlertSent,
                PriceAlertSettings,
            )
            from features.ratings.models import RatingAlertSettings, RatingRelease
            from features.users.models import TinvestUser, User

            __all__ = [
                Issuer,
                IssuerBond,
                OfferAlertSettings,
                BondLastPrice,
                BondPriceHistory,
                PriceAlertSent,
                PriceAlertSettings,
                RatingAlertSettings,
                RatingRelease,
                FnsAlertSettings,
                FnsBlockingRecord,
                User,
                TinvestUser,
            ]
        except ImportError as e:
            logger.critical(f"Критическая ошибка импорта моделей при инициализации БД: {e}")
            raise e
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Таблицы базы данных созданы")

    async def close(self) -> None:
        """Закрывает соединение с базой данных."""
        await self.engine.dispose()


db_manager = DatabaseManager(config.database_url)


async def get_session() -> AsyncGenerator[AsyncSession]:
    """Генератор сессий базы данных."""
    async with db_manager.session_factory() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка сессии БД: {e}")
            raise
        finally:
            await session.close()


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Контекст-менеджер для одной сессии БД.

    Обёртка над ``get_session()`` для удобства: позволяет писать
    ``async with session_scope() as session:`` вместо
    ``async for session in get_session():``.

    Откат транзакции при исключении и закрытие сессии выполняются
    внутри ``get_session()``.
    """
    async for session in get_session():
        yield session
        return
