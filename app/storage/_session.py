"""Утилиты для работы с сессиями БД внутри репозиториев."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from core.database import get_session
from sqlalchemy.ext.asyncio import AsyncSession


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
