"""Настройка подключения к базе данных."""

import logging
from collections.abc import AsyncGenerator
from pathlib import Path

from models.base import Base
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logger = logging.getLogger(__name__)

# Путь к директории data относительно этого файла (core/database.py -> app/data/)
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_URL = f"sqlite+aiosqlite:///{DATA_DIR}/bot_data.db"


class DatabaseManager:
    """Менеджер базы данных."""

    def __init__(self, database_url: str = DATABASE_URL):
        """Инициализирует менеджер базы данных."""
        self.engine = create_async_engine(
            database_url,
            echo=False,
            future=True,
        )
        self.session_factory = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def create_tables(self) -> None:
        """Создает все таблицы в базе данных."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Таблицы базы данных созданы")

    async def close(self) -> None:
        """Закрывает соединение с базой данных."""
        await self.engine.dispose()


db_manager = DatabaseManager()


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
