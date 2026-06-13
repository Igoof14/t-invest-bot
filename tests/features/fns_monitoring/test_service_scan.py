"""Тесты разовой проверки эмитентов пользователя (scan_user)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from features.fns_monitoring import service as service_module
from features.fns_monitoring.service import FnsBlockingMonitorService

pytestmark = pytest.mark.asyncio


def _issuer(inn: str | None, **kw: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "id": 1,
        "inn": inn,
        "short_title": "ООО ТЕСТ",
        "title": "ООО ТЕСТ ПОЛНОЕ",
    }
    base.update(kw)
    return SimpleNamespace(**base)


def _bond(**kw: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "name": "ТЕСТ-БО-01",
        "isin": "RU000A0TEST1",
        "figi": "BBG00TEST",
        "ticker": "RU000A0TEST1",
    }
    base.update(kw)
    return SimpleNamespace(**base)


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    *,
    token: str | None = "tkn",
    held: set[str] | None = None,
    issuers: list[SimpleNamespace] | None = None,
    bonds: list[SimpleNamespace] | None = None,
    run_result: object = None,
) -> None:
    held = held if held is not None else {"BBG00TEST"}
    issuers = issuers if issuers is not None else [_issuer("7700000000")]
    bonds = bonds if bonds is not None else [_bond()]

    async def _token(telegram_id: int) -> str | None:
        return token

    async def _portfolio(tok: str, telegram_id: int | None = None) -> set[str]:
        return held

    async def _issuers(identifiers: set[str]) -> list[SimpleNamespace]:
        return issuers

    async def _bonds(issuer_id: int) -> list[SimpleNamespace]:
        return bonds

    async def _run(inn: str, retries: int = 3) -> object:
        if isinstance(run_result, Exception):
            raise run_result
        return run_result if run_result is not None else {"rows": []}

    monkeypatch.setattr(
        service_module.BotUserRepository, "get_token_by_telegram_id", _token
    )
    monkeypatch.setattr(service_module, "get_portfolio_bond_identifiers", _portfolio)
    monkeypatch.setattr(
        service_module.IssuerRepository, "get_issuers_by_identifiers", _issuers
    )
    monkeypatch.setattr(service_module.IssuerRepository, "list_bonds", _bonds)
    monkeypatch.setattr(service_module, "run", _run)


async def test_scan_no_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, token=None)
    report = await FnsBlockingMonitorService(None).scan_user(1)  # type: ignore[arg-type]
    assert report.no_token is True


async def test_scan_no_bonds(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, held=set())
    report = await FnsBlockingMonitorService(None).scan_user(1)  # type: ignore[arg-type]
    assert report.no_bonds is True


async def test_scan_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, run_result={"rows": []})
    report = await FnsBlockingMonitorService(None).scan_user(1)  # type: ignore[arg-type]
    assert report.checked == 1
    assert report.blocked == []


async def test_scan_finds_block(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = {
        "rows": [
            {"BIK": "044525225", "NOMER": "12345", "NAIM": "ООО ТЕСТ", "SALDOENS": "100.0"}
        ]
    }
    _patch(monkeypatch, run_result=rows)
    report = await FnsBlockingMonitorService(None).scan_user(1)  # type: ignore[arg-type]

    assert report.checked == 1
    assert len(report.blocked) == 1
    alert = report.blocked[0]
    assert alert.inn == "7700000000"
    assert alert.entity_name == "ООО ТЕСТ"
    assert alert.matched_bond_names == ["ТЕСТ-БО-01"]
    assert alert.orders[0].block_uid == "044525225:12345"


async def test_scan_skips_failed_inn(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, run_result=RuntimeError("captcha_failed"))
    report = await FnsBlockingMonitorService(None).scan_user(1)  # type: ignore[arg-type]
    assert report.checked == 0
    assert report.blocked == []
