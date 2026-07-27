"""Общие фикстуры тестов."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import date

import pytest
import pytest_asyncio
from core.config import config
from core.database import Base
from features.offer_warning.schemas import BondOffer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


@pytest.fixture(autouse=True)
def disable_analytics(monkeypatch: pytest.MonkeyPatch) -> None:
    """Отключает запись продуктовых событий во всех тестах по умолчанию.

    Иначе каждый тест хендлера пытался бы писать в реальную БД. Тесты самой
    аналитики включают её обратно фикстурой ``enable_analytics``.
    """
    monkeypatch.setattr(config, "analytics_enabled", False)


@pytest.fixture
def enable_analytics(monkeypatch: pytest.MonkeyPatch) -> None:
    """Включает аналитику и трекинг админа для тестов самой фичи."""
    monkeypatch.setattr(config, "analytics_enabled", True)
    monkeypatch.setattr(config, "analytics_track_admin", True)


@pytest.fixture
def offer_factory() -> Callable[..., BondOffer]:
    """Возвращает фабрику ``BondOffer`` с дефолтами, переопределяемыми по полям."""

    def _make(**overrides: object) -> BondOffer:
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
        return BondOffer(**defaults)  # type: ignore[arg-type]

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
        "features.analytics.repository.session_scope",
        "features.offer_warning.repository.session_scope",
        "features.ratings.repository.session_scope",
        "features.fns_monitoring.repository.session_scope",
        "features.users.repository.session_scope",
    ):
        monkeypatch.setattr(target, _test_session_scope)

    yield

    await engine.dispose()
