"""Тесты оркестратора уведомлений об изменении рейтингов НРА."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from features.rating_nra import service as service_module
from features.rating_nra.service import RatingAlertService
from features.rating_nra.schemas import RatingEvent, ReleaseStub


def _stub(post_id: int, modified: str = "2026-06-03T10:00:00") -> ReleaseStub:
    return ReleaseStub(
        post_id=post_id,
        url=f"https://x/{post_id}/",
        modified=datetime.fromisoformat(modified),
    )


def _event(post_id: int = 1, inn: str | None = "7700000000") -> RatingEvent:
    return RatingEvent(
        post_id=post_id,
        url=f"https://x/{post_id}/",
        entity_name="Эмитент",
        inn=inn,
        rating_action="Понижен",
        modified=datetime(2026, 6, 3, 10, 0, 0),
    )


def _bond(figi: str = "BBG00X", isin: str = "RU000A1", name: str = "Бонд 1Р") -> MagicMock:
    bond = MagicMock()
    bond.figi = figi
    bond.ticker = isin
    bond.isin = isin
    bond.name = name
    return bond


def _patch_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    stubs: list[ReleaseStub],
    events: list[RatingEvent],
) -> None:
    client = MagicMock()
    client.iter_release_stubs = AsyncMock(return_value=stubs)
    client.fetch_many = AsyncMock(return_value=events)

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(service_module, "NraClient", MagicMock(return_value=cm))


def _patch_repo(monkeypatch: pytest.MonkeyPatch, *, known: dict) -> AsyncMock:
    monkeypatch.setattr(
        service_module.NraReleaseRepository,
        "get_modified_map",
        AsyncMock(return_value=known),
    )
    upsert = AsyncMock()
    monkeypatch.setattr(service_module.NraReleaseRepository, "upsert_many", upsert)
    return upsert


async def test_first_run_seeds_without_alerting(monkeypatch: pytest.MonkeyPatch) -> None:
    upsert = _patch_repo(monkeypatch, known={})  # пустая БД → первый запуск
    _patch_client(monkeypatch, stubs=[_stub(1)], events=[_event()])

    notifier = MagicMock()
    notifier.send = AsyncMock()
    await RatingAlertService(MagicMock(), notifier=notifier).run_check()

    upsert.assert_awaited_once()
    notifier.send.assert_not_awaited()


async def test_no_changes_does_not_alert(monkeypatch: pytest.MonkeyPatch) -> None:
    # Релиз уже известен с тем же modified → ничего не выбрано.
    _patch_repo(monkeypatch, known={1: "2026-06-03T10:00:00"})
    _patch_client(monkeypatch, stubs=[_stub(1)], events=[])

    notifier = MagicMock()
    notifier.send = AsyncMock()
    await RatingAlertService(MagicMock(), notifier=notifier).run_check()

    notifier.send.assert_not_awaited()


async def test_alerts_holder_of_matching_bond(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_repo(monkeypatch, known={99: "old"})  # не первый запуск
    _patch_client(monkeypatch, stubs=[_stub(1)], events=[_event()])

    issuer = MagicMock(id=5)
    monkeypatch.setattr(
        service_module.IssuerRepository, "get_issuer_by_inn", AsyncMock(return_value=issuer)
    )
    monkeypatch.setattr(
        service_module.IssuerRepository, "list_bonds", AsyncMock(return_value=[_bond()])
    )
    monkeypatch.setattr(
        service_module.RatingAlertSettingsRepository,
        "list_users_with_alerts_enabled",
        AsyncMock(return_value=[111, 222]),
    )
    monkeypatch.setattr(
        service_module.BotUserRepository,
        "get_token_by_telegram_id",
        AsyncMock(return_value="token"),
    )
    # 111 держит бумагу (по figi), 222 — нет.
    monkeypatch.setattr(
        service_module,
        "get_portfolio_bond_identifiers",
        AsyncMock(side_effect=[{"BBG00X"}, {"OTHER"}]),
    )

    notifier = MagicMock()
    notifier.send = AsyncMock()
    await RatingAlertService(MagicMock(), notifier=notifier).run_check()

    notifier.send.assert_awaited_once()
    telegram_id, changes = notifier.send.await_args.args
    assert telegram_id == 111
    assert changes[0].matched_bond_names == ["Бонд 1Р"]


async def test_resolves_issuer_by_one_of_several_isins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Релиз без ИНН, но с несколькими ISIN: эмитент найден по второму.
    event = RatingEvent(
        post_id=1,
        url="https://x/1/",
        entity_name="Эмитент",
        inn=None,
        isins=["RU000MISS", "RU000HIT"],
        modified=datetime(2026, 6, 3, 10, 0, 0),
    )
    _patch_repo(monkeypatch, known={99: "old"})
    _patch_client(monkeypatch, stubs=[_stub(1)], events=[event])

    issuer = MagicMock(id=5)
    by_isin = AsyncMock(side_effect=[None, issuer])  # промах, затем попадание
    monkeypatch.setattr(service_module.IssuerRepository, "get_issuer_by_isin", by_isin)
    monkeypatch.setattr(
        service_module.IssuerRepository, "list_bonds", AsyncMock(return_value=[_bond()])
    )
    monkeypatch.setattr(
        service_module.RatingAlertSettingsRepository,
        "list_users_with_alerts_enabled",
        AsyncMock(return_value=[111]),
    )
    monkeypatch.setattr(
        service_module.BotUserRepository,
        "get_token_by_telegram_id",
        AsyncMock(return_value="token"),
    )
    monkeypatch.setattr(
        service_module,
        "get_portfolio_bond_identifiers",
        AsyncMock(return_value={"BBG00X"}),
    )

    notifier = MagicMock()
    notifier.send = AsyncMock()
    await RatingAlertService(MagicMock(), notifier=notifier).run_check()

    assert by_isin.await_count == 2  # перебрал оба ISIN
    notifier.send.assert_awaited_once()


async def test_skips_event_with_unknown_issuer(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_repo(monkeypatch, known={99: "old"})
    _patch_client(monkeypatch, stubs=[_stub(1)], events=[_event()])

    monkeypatch.setattr(
        service_module.IssuerRepository, "get_issuer_by_inn", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        service_module.IssuerRepository, "get_issuer_by_isin", AsyncMock(return_value=None)
    )
    get_users = AsyncMock(return_value=[111])
    monkeypatch.setattr(
        service_module.RatingAlertSettingsRepository,
        "list_users_with_alerts_enabled",
        get_users,
    )

    notifier = MagicMock()
    notifier.send = AsyncMock()
    await RatingAlertService(MagicMock(), notifier=notifier).run_check()

    notifier.send.assert_not_awaited()
    get_users.assert_not_awaited()  # до перебора юзеров не дошли


async def test_user_error_isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_repo(monkeypatch, known={99: "old"})
    _patch_client(monkeypatch, stubs=[_stub(1)], events=[_event()])

    monkeypatch.setattr(
        service_module.IssuerRepository,
        "get_issuer_by_inn",
        AsyncMock(return_value=MagicMock(id=5)),
    )
    monkeypatch.setattr(
        service_module.IssuerRepository, "list_bonds", AsyncMock(return_value=[_bond()])
    )
    monkeypatch.setattr(
        service_module.RatingAlertSettingsRepository,
        "list_users_with_alerts_enabled",
        AsyncMock(return_value=[111, 222]),
    )
    monkeypatch.setattr(
        service_module.BotUserRepository,
        "get_token_by_telegram_id",
        AsyncMock(side_effect=[RuntimeError("boom"), "token"]),
    )
    monkeypatch.setattr(
        service_module,
        "get_portfolio_bond_identifiers",
        AsyncMock(return_value={"BBG00X"}),
    )

    notifier = MagicMock()
    notifier.send = AsyncMock()
    await RatingAlertService(MagicMock(), notifier=notifier).run_check()

    # Первый пользователь упал, второй всё равно получил алерт.
    notifier.send.assert_awaited_once()
    assert notifier.send.await_args.args[0] == 222
