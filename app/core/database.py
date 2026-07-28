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
            # Параметры пула вынесены в конфиг: их приходится подбирать под
            # конкретный деплой, а не под код. См. комментарий в ``Settings``.
            pool_size=config.db_pool_size,
            max_overflow=config.db_max_overflow,
            pool_pre_ping=config.db_pool_pre_ping,
            pool_recycle=config.db_pool_recycle,
            pool_timeout=config.db_pool_timeout,
        )
        self.session_factory = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def create_tables(self) -> None:
        """Создает все таблицы в базе данных."""
        try:
            # Укажите здесь актуальные пути в зависимости от вашей структуры.
            # Если перешли на Feature-driven, пути будут такими:
            from features.analytics.models import BotEvent
            from features.fns_monitoring.models import (
                FnsAlertSettings,
                FnsBlockingRecord,
            )
            from features.offer_warning.models import OfferAlertSettings
            from features.price_monitoring.models import PriceAlertSettings
            from features.ratings.models import RatingAlertSettings, RatingRelease

            # `bot_users` тут намеренно нет: её схемой владеет и мигрирует bondelo-backend.
            from features.users.models import TinvestUser

            __all__ = [
                BotEvent,
                OfferAlertSettings,
                PriceAlertSettings,
                RatingAlertSettings,
                RatingRelease,
                FnsAlertSettings,
                FnsBlockingRecord,
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

    Основной способ работы с БД в хендлерах и репозиториях; ``get_session()``
    оставлен как зависимость для HTTP-слоя.

    Сессия создаётся напрямую, а не через ``get_session()``: выход из
    ``async for`` по ``return`` бросал асинхронный генератор недоработанным,
    поэтому его ``finally`` (и возврат соединения в пул) откладывался до
    сборки мусора. Под нагрузкой соединения копились до
    ``pool_size + max_overflow``, и следующие обращения к БД вставали в
    ожидание на ``pool_timeout``.
    """
    async with db_manager.session_factory() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка сессии БД: {e}")
            raise
