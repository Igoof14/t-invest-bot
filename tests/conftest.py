"""Общие фикстуры для тестов offer_warning."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import date

import pytest
import pytest_asyncio
from core.clients.moex.moex_bonds import MoexBondOffer
from core.database import Base
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


@pytest.fixture
def offer_factory() -> Callable[..., MoexBondOffer]:
    """Возвращает фабрику ``MoexBondOffer`` с дефолтами, переопределяемыми по полям."""

    def _make(**overrides: object) -> MoexBondOffer:
        defaults: dict[str, object] = {
            "isin": "RU000A0JX0J2",
            "name": "Тестовая облигация",
            "offerdate": date(2026, 6, 15),
            "facevalue": 1000.0,
            "faceunit": "rub",
            "price": 100.0,
            "secid": "TEST01",
            "primary_boardid": "TQCB",
        }
        defaults.update(overrides)
        return MoexBondOffer(**defaults)  # type: ignore[arg-type]

    return _make


@pytest_asyncio.fixture
async def patch_session_scope(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    """Подменяет ``session_scope`` репозитория на in-memory SQLite.

    Все сессии используют единое соединение (``StaticPool``), поэтому данные
    сохраняются между вызовами в рамках одного теста.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    sessionmaker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    @asynccontextmanager
    async def _test_session_scope() -> AsyncIterator[AsyncSession]:
        async with sessionmaker() as session:
            yield session

    # Патчим session_scope во всех репозиториях, использующих in-memory БД.
    for target in (
        "features.offer_warning.repository.session_scope",
        "features.issuers.repository.session_scope",
        "features.rating_nra.repository.session_scope",
        "features.ratings.repository.session_scope",
    ):
        monkeypatch.setattr(target, _test_session_scope)

    yield

    await engine.dispose()
