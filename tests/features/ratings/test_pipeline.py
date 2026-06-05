"""Тесты общего конвейера: select_changed / resolve_events / notify_subscribers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from features.ratings import pipeline
from features.ratings.enums import RatingAgency
from features.ratings.events import ChangeType, RatingEvent, ReleaseStub
from features.ratings.pipeline import (
    ResolvedEvent,
    notify_subscribers,
    resolve_events,
    select_changed,
)


def test_select_changed_picks_new_and_keeps_order() -> None:
    stubs = [ReleaseStub(uid="a", url="x"), ReleaseStub(uid="b", url="y")]
    selected, change_by_uid = select_changed(stubs, {"a": None}, early_stop=10)

    assert [s.uid for s in selected] == ["b"]
    assert change_by_uid["b"] is ChangeType.NEW


async def test_resolve_events_matches_issuer_by_inn(monkeypatch: pytest.MonkeyPatch) -> None:
    issuer = MagicMock(id=5)
    bond = MagicMock(figi="BBG00X", ticker="T1", isin="RU000A1", name="Бонд 1Р")
    monkeypatch.setattr(
        pipeline.IssuerRepository, "get_issuer_by_inn", AsyncMock(return_value=issuer)
    )
    monkeypatch.setattr(
        pipeline.IssuerRepository, "list_bonds", AsyncMock(return_value=[bond])
    )

    event = RatingEvent(uid="1", url="u", inn="7700000000")
    resolved = await resolve_events([event], {"1": ChangeType.NEW})

    assert len(resolved) == 1
    assert "BBG00X" in resolved[0].identifiers


async def test_resolve_events_skips_unknown_issuer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        pipeline.IssuerRepository, "get_issuer_by_inn", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        pipeline.IssuerRepository, "get_issuer_by_isin", AsyncMock(return_value=None)
    )

    event = RatingEvent(uid="1", url="u", inn="0000000000", isins=["RU000MISS"])
    assert await resolve_events([event], {"1": ChangeType.NEW}) == []


async def test_notify_subscribers_only_holders(monkeypatch: pytest.MonkeyPatch) -> None:
    resolved = [
        ResolvedEvent(
            event=RatingEvent(uid="1", url="u", entity_name="Эмитент"),
            change_type=ChangeType.NEW,
            identifiers={"BBG00X"},
            name_by_id={"BBG00X": "Бонд 1Р"},
        )
    ]
    monkeypatch.setattr(
        pipeline.RatingAlertSettingsRepository,
        "list_users_with_alerts_enabled",
        AsyncMock(return_value=[111, 222]),
    )
    monkeypatch.setattr(
        pipeline.BotUserRepository,
        "get_token_by_telegram_id",
        AsyncMock(return_value="token"),
    )
    # 111 держит бумагу, 222 — нет.
    monkeypatch.setattr(
        pipeline,
        "get_portfolio_bond_identifiers",
        AsyncMock(side_effect=[{"BBG00X"}, {"OTHER"}]),
    )

    notifier = MagicMock()
    notifier.send = AsyncMock()
    await notify_subscribers(MagicMock(), RatingAgency.NKR, resolved, notifier)

    notifier.send.assert_awaited_once()
    telegram_id, agency_name, changes = notifier.send.await_args.args
    assert telegram_id == 111
    assert agency_name == "НКР"
    assert changes[0].matched_bond_names == ["Бонд 1Р"]
