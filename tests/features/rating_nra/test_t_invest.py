"""Тесты получения идентификаторов облигаций портфеля через T-Invest."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from features.rating_nra import t_invest
from features.rating_nra.t_invest import get_portfolio_bond_identifiers


def _position(instrument_type: str, figi: str = "", ticker: str = "") -> MagicMock:
    pos = MagicMock()
    pos.instrument_type = instrument_type
    pos.figi = figi
    pos.ticker = ticker
    return pos


def _account(account_id: str) -> MagicMock:
    acc = MagicMock()
    acc.id = account_id
    return acc


def _patch_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    accounts: list[MagicMock],
    get_portfolio: AsyncMock,
) -> None:
    client = MagicMock()
    client.users.get_accounts = AsyncMock(return_value=MagicMock(accounts=accounts))
    client.operations.get_portfolio = get_portfolio

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(t_invest, "AsyncClient", MagicMock(return_value=cm))


async def test_collects_figi_and_ticker_of_bonds(monkeypatch: pytest.MonkeyPatch) -> None:
    portfolio = MagicMock(
        positions=[
            _position("bond", figi="BBG00X", ticker="RU000A105RV3"),
            _position("share", figi="BBG00AAPL", ticker="AAPL"),  # не облигация
            _position("bond", figi="BBG00X", ticker="RU000A105RV3"),  # дубль
            _position("bond", figi="", ticker="RU000A0JX0J2"),  # только тикер
        ]
    )
    _patch_client(
        monkeypatch,
        accounts=[_account("acc1")],
        get_portfolio=AsyncMock(return_value=portfolio),
    )

    result = await get_portfolio_bond_identifiers("token")
    assert result == {"BBG00X", "RU000A105RV3", "RU000A0JX0J2"}


async def test_continues_when_one_account_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    good = MagicMock(positions=[_position("bond", figi="BBG00G")])
    _patch_client(
        monkeypatch,
        accounts=[_account("bad"), _account("good")],
        get_portfolio=AsyncMock(side_effect=[RuntimeError("boom"), good]),
    )

    result = await get_portfolio_bond_identifiers("token")
    assert result == {"BBG00G"}


async def test_returns_empty_on_outer_error(monkeypatch: pytest.MonkeyPatch) -> None:
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(side_effect=RuntimeError("auth failed"))
    cm.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(t_invest, "AsyncClient", MagicMock(return_value=cm))

    result = await get_portfolio_bond_identifiers("token")
    assert result == set()
