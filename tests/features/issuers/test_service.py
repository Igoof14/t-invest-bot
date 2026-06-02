"""Тесты сервиса синхронизации реестра эмитентов."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from core.clients.moex.moex_bonds import MoexEmitter
from features.issuers import service
from features.issuers.service import IssuerSyncService


def _bond(isin: str, figi: str = "F", ticker: str = "T", name: str = "N") -> SimpleNamespace:
    return SimpleNamespace(isin=isin, figi=figi, ticker=ticker, name=name)


def _emitter(emitter_id: int, secid: str) -> MoexEmitter:
    return MoexEmitter(emitter_id=emitter_id, inn=str(emitter_id), secid=secid)


def _patch_moex(monkeypatch: pytest.MonkeyPatch, issuers_by_isin: dict) -> None:
    client = MagicMock()
    client.get_many_issuers = AsyncMock(return_value=issuers_by_isin)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(service, "MoexClient", MagicMock(return_value=cm))


async def test_sync_returns_zero_without_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        IssuerSyncService, "_resolve_token", AsyncMock(return_value=None)
    )
    upsert_bond = AsyncMock()
    monkeypatch.setattr(service.IssuerRepository, "upsert_bond", upsert_bond)

    assert await IssuerSyncService.sync_all_issuers() == (0, 0)
    upsert_bond.assert_not_called()


async def test_sync_dedups_issuers_and_saves_bonds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        IssuerSyncService, "_resolve_token", AsyncMock(return_value="token")
    )
    bonds = [_bond("A"), _bond("B"), _bond("C"), _bond("D")]
    monkeypatch.setattr(
        IssuerSyncService, "_fetch_all_bonds", AsyncMock(return_value=bonds)
    )
    # A и B — один эмитент (100), C — другой (200), D — без эмитента.
    _patch_moex(
        monkeypatch,
        {
            "A": _emitter(100, "A"),
            "B": _emitter(100, "B"),
            "C": _emitter(200, "C"),
            "D": None,
        },
    )

    upsert_issuer = AsyncMock(side_effect=lambda e: e.emitter_id)
    upsert_bond = AsyncMock()
    monkeypatch.setattr(service.IssuerRepository, "upsert_issuer", upsert_issuer)
    monkeypatch.setattr(service.IssuerRepository, "upsert_bond", upsert_bond)

    issuers_count, bonds_count = await IssuerSyncService.sync_all_issuers()

    assert (issuers_count, bonds_count) == (2, 4)
    # upsert_issuer вызван один раз на уникальный emitter_id (100, 200).
    assert upsert_issuer.await_count == 2
    assert upsert_bond.await_count == 4


async def test_sync_links_bond_to_issuer_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        IssuerSyncService, "_resolve_token", AsyncMock(return_value="token")
    )
    monkeypatch.setattr(
        IssuerSyncService, "_fetch_all_bonds", AsyncMock(return_value=[_bond("A")])
    )
    _patch_moex(monkeypatch, {"A": _emitter(100, "A")})
    monkeypatch.setattr(
        service.IssuerRepository, "upsert_issuer", AsyncMock(return_value=777)
    )
    upsert_bond = AsyncMock()
    monkeypatch.setattr(service.IssuerRepository, "upsert_bond", upsert_bond)

    await IssuerSyncService.sync_all_issuers()

    _, kwargs = upsert_bond.call_args
    assert kwargs["isin"] == "A"
    assert kwargs["issuer_id"] == 777
