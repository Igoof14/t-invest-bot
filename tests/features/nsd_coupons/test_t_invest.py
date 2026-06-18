"""Тесты сбора купонного календаря из T-Invest."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from features.nsd_coupons import t_invest
from features.nsd_coupons.t_invest import collect_coupon_plans


@pytest.fixture(autouse=True)
def _reset_bonds_cache() -> None:
    """Сбрасывает модульный кэш каталога облигаций перед каждым тестом."""
    t_invest._bonds_cache = {}
    t_invest._bonds_cached_at = None


def _bond(figi: str, isin: str, name: str) -> MagicMock:
    bond = MagicMock()
    bond.figi = figi
    bond.isin = isin
    bond.name = name
    return bond


def _position(instrument_type: str, figi: str) -> MagicMock:
    pos = MagicMock()
    pos.instrument_type = instrument_type
    pos.figi = figi
    return pos


def _coupon(number: int, dt: datetime, units: int) -> MagicMock:
    coupon = MagicMock()
    coupon.coupon_number = number
    coupon.coupon_date = dt
    coupon.pay_one_bond = MagicMock(units=units, nano=0)
    return coupon


def _patch_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    bonds: list[MagicMock],
    positions: list[MagicMock],
    coupons: list[MagicMock],
) -> MagicMock:
    client = MagicMock()
    client.instruments.bonds = AsyncMock(return_value=MagicMock(instruments=bonds))
    client.users.get_accounts = AsyncMock(
        return_value=MagicMock(accounts=[MagicMock(id="acc1")])
    )
    client.operations.get_portfolio = AsyncMock(
        return_value=MagicMock(positions=positions)
    )
    client.instruments.get_bond_coupons = AsyncMock(
        return_value=MagicMock(events=coupons)
    )
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(t_invest, "AsyncClient", MagicMock(return_value=cm))
    monkeypatch.setattr(
        t_invest.BotUserRepository,
        "get_token_by_telegram_id",
        AsyncMock(return_value="token"),
    )
    return client


async def test_collect_skips_non_ru_and_non_bond(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_client(
        monkeypatch,
        bonds=[
            _bond("FG1", "RU000A105P23", "Автодор"),
            _bond("FG2", "XS0000000000", "Eurobond"),  # не RU → пропуск
        ],
        positions=[
            _position("bond", "FG1"),
            _position("share", "FG9"),  # не облигация → пропуск
            _position("bond", "FG2"),  # не RU ISIN → пропуск
        ],
        coupons=[_coupon(1, datetime(2026, 6, 19), 5)],
    )

    plans = await collect_coupon_plans(101)

    assert len(plans) == 1
    assert plans[0].isin == "RU000A105P23"
    assert plans[0].figi == "FG1"
    assert plans[0].coupon_number == 1
    assert plans[0].amount == 5.0
    assert plans[0].bond_name == "Автодор"


async def test_collect_returns_empty_without_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        t_invest.BotUserRepository,
        "get_token_by_telegram_id",
        AsyncMock(return_value=None),
    )
    assert await collect_coupon_plans(101) == []


async def test_bonds_catalog_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _patch_client(
        monkeypatch,
        bonds=[_bond("FG1", "RU000A105P23", "Автодор")],
        positions=[_position("bond", "FG1")],
        coupons=[_coupon(1, datetime(2026, 6, 19), 5)],
    )

    await collect_coupon_plans(101)
    await collect_coupon_plans(101)

    # Каталог инструментов тянется один раз и переиспользуется из кэша.
    assert client.instruments.bonds.await_count == 1
