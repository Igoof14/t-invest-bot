"""Тесты получения облигаций из портфеля через T-Invest API."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from features.offer_warning import t_invest
from features.offer_warning.t_invest import get_portfolio_bond_isins


def _position(instrument_type: str, ticker: str) -> MagicMock:
    """Создаёт мок позиции портфеля."""
    pos = MagicMock()
    pos.instrument_type = instrument_type
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
    """Подменяет AsyncClient на мок-контекст-менеджер с заданным поведением."""
    client = MagicMock()
    client.users.get_accounts = AsyncMock(
        return_value=MagicMock(accounts=accounts)
    )
    client.operations.get_portfolio = get_portfolio

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(t_invest, "AsyncClient", MagicMock(return_value=cm))


async def test_returns_unique_bond_tickers(monkeypatch: pytest.MonkeyPatch) -> None:
    portfolio = MagicMock(
        positions=[
            _position("bond", "SU26240"),
            _position("share", "AAPL"),  # не облигация → пропуск
            _position("bond", ""),  # пустой тикер → пропуск
            _position("bond", "SU26240"),  # дубль
            _position("bond", "RU000A0JX0J2"),
        ]
    )
    _patch_client(
        monkeypatch,
        accounts=[_account("acc1")],
        get_portfolio=AsyncMock(return_value=portfolio),
    )

    result = await get_portfolio_bond_isins("token")
    assert sorted(result) == ["RU000A0JX0J2", "SU26240"]


async def test_continues_when_one_account_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    good_portfolio = MagicMock(positions=[_position("bond", "SU26240")])
    _patch_client(
        monkeypatch,
        accounts=[_account("bad"), _account("good")],
        get_portfolio=AsyncMock(side_effect=[RuntimeError("boom"), good_portfolio]),
    )

    result = await get_portfolio_bond_isins("token")
    assert result == ["SU26240"]


async def test_returns_empty_on_outer_error(monkeypatch: pytest.MonkeyPatch) -> None:
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(side_effect=RuntimeError("auth failed"))
    cm.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(t_invest, "AsyncClient", MagicMock(return_value=cm))

    result = await get_portfolio_bond_isins("token")
    assert result == []
