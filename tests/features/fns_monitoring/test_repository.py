"""Тесты репозиториев подписок и состояния блокировок ФНС."""

from __future__ import annotations

import pytest
from features.fns_monitoring.events import BlockingOrder
from features.fns_monitoring.repository import (
    FnsAlertSettingsRepository,
    FnsBlockingRepository,
)

pytestmark = pytest.mark.usefixtures("patch_session_scope")


def _order(uid: str = "BIK1:1", inn: str = "7700000000", **overrides: object) -> BlockingOrder:
    data: dict[str, object] = {"inn": inn, "block_uid": uid, "nomer": uid.split(":")[-1]}
    data.update(overrides)
    return BlockingOrder(**data)  # type: ignore[arg-type]


async def test_toggle_creates_then_flips() -> None:
    assert await FnsAlertSettingsRepository.toggle(111) is True
    assert await FnsAlertSettingsRepository.is_enabled(111) is True
    assert await FnsAlertSettingsRepository.toggle(111) is False
    assert await FnsAlertSettingsRepository.is_enabled(111) is False


async def test_list_users_with_alerts_enabled() -> None:
    await FnsAlertSettingsRepository.toggle(1)  # on
    await FnsAlertSettingsRepository.toggle(2)  # on
    await FnsAlertSettingsRepository.toggle(2)  # off

    assert await FnsAlertSettingsRepository.list_users_with_alerts_enabled() == [1]


async def test_has_any_reflects_history() -> None:
    assert await FnsBlockingRepository.has_any("7700000000") is False
    await FnsBlockingRepository.sync("7700000000", [_order()])
    assert await FnsBlockingRepository.has_any("7700000000") is True


async def test_sync_returns_only_new_orders() -> None:
    new = await FnsBlockingRepository.sync("7700000000", [_order("A:1"), _order("B:2")])
    assert {o.block_uid for o in new} == {"A:1", "B:2"}

    # Повторный прогон тех же блокировок — ничего нового.
    again = await FnsBlockingRepository.sync("7700000000", [_order("A:1"), _order("B:2")])
    assert again == []

    # Появилась новая блокировка — возвращается только она.
    third = await FnsBlockingRepository.sync(
        "7700000000", [_order("A:1"), _order("B:2"), _order("C:3")]
    )
    assert {o.block_uid for o in third} == {"C:3"}


async def test_sync_resolves_disappeared_blocks() -> None:
    await FnsBlockingRepository.sync("7700000000", [_order("A:1"), _order("B:2")])

    # B исчезла из ответа — снимается; A остаётся.
    new = await FnsBlockingRepository.sync("7700000000", [_order("A:1")])
    assert new == []

    # B снова появилась — считается новой (реактивация).
    reactivated = await FnsBlockingRepository.sync(
        "7700000000", [_order("A:1"), _order("B:2")]
    )
    assert {o.block_uid for o in reactivated} == {"B:2"}
