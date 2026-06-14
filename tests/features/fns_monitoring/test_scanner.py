"""Тесты непрерывного сканера блокировок ФНС."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from features.fns_monitoring import scanner as scanner_module
from features.fns_monitoring.events import BlockingOrder, ResolvedBlock
from features.fns_monitoring.scanner import (
    FnsScanner,
    in_window,
    seconds_until_open,
    should_skip_revisit,
)

_MSK = ZoneInfo("Europe/Moscow")


def _at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 6, 14, hour, minute, tzinfo=_MSK)


# --- чистые хелперы ---


def test_in_window() -> None:
    assert in_window(_at(8)) is True
    assert in_window(_at(19, 59)) is True
    assert in_window(_at(7, 59)) is False
    assert in_window(_at(20)) is False
    assert in_window(_at(23)) is False


def test_seconds_until_open_inside_is_zero() -> None:
    assert seconds_until_open(_at(12)) == 0.0


def test_seconds_until_open_before_window() -> None:
    assert seconds_until_open(_at(7)) == 3600.0


def test_seconds_until_open_after_window_is_next_day() -> None:
    # 21:00 → завтра 08:00 = 11 часов.
    assert seconds_until_open(_at(21)) == 11 * 3600.0


def test_should_skip_revisit() -> None:
    now = _at(12)
    assert should_skip_revisit("77", now, {}) is False
    assert should_skip_revisit("77", now, {"77": now - timedelta(minutes=10)}) is True
    assert should_skip_revisit("77", now, {"77": now - timedelta(minutes=40)}) is False


# --- _check_and_notify ---


class _FakeNotifier:
    def __init__(self) -> None:
        self.sent: list[tuple[int, int]] = []

    async def send(self, telegram_id: int, alerts: list[object]) -> bool:
        self.sent.append((telegram_id, len(alerts)))
        return True


def _order() -> BlockingOrder:
    return BlockingOrder(inn="77", block_uid="B:1", nomer="1", entity_name="ООО ТЕСТ")


def _scanner_with() -> tuple[FnsScanner, _FakeNotifier]:
    sc = FnsScanner(None)  # type: ignore[arg-type]
    notifier = _FakeNotifier()
    sc._notifier = notifier  # type: ignore[assignment]
    sc._issuer_by_inn = {"77": SimpleNamespace(id=1, inn="77")}
    sc._held_by_user = {123: {"BBG"}}
    return sc, notifier


async def test_check_and_notify_sends_on_new_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sc, notifier = _scanner_with()

    async def _has_any(inn: str) -> bool:
        return True

    async def _sync(inn: str, orders: list[BlockingOrder]) -> list[BlockingOrder]:
        return [_order()]

    async def _resolve(issuer: object, new_orders: list[BlockingOrder]) -> ResolvedBlock:
        return ResolvedBlock(
            inn="77",
            entity_name="ООО ТЕСТ",
            new_orders=new_orders,
            identifiers={"BBG"},
            name_by_id={"BBG": "ТЕСТ-БО-01"},
        )

    monkeypatch.setattr(scanner_module.FnsBlockingRepository, "has_any", _has_any)
    monkeypatch.setattr(scanner_module.FnsBlockingRepository, "sync", _sync)
    monkeypatch.setattr(scanner_module, "resolve_block", _resolve)

    await sc._check_and_notify("77", {"rows": [{"NOMER": "1"}]})

    assert notifier.sent == [(123, 1)]


async def test_check_and_notify_silent_on_first_observation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sc, notifier = _scanner_with()

    async def _has_any(inn: str) -> bool:
        return False

    async def _sync(inn: str, orders: list[BlockingOrder]) -> list[BlockingOrder]:
        return [_order()]

    monkeypatch.setattr(scanner_module.FnsBlockingRepository, "has_any", _has_any)
    monkeypatch.setattr(scanner_module.FnsBlockingRepository, "sync", _sync)

    await sc._check_and_notify("77", {"rows": [{"NOMER": "1"}]})

    assert notifier.sent == []


async def test_check_and_notify_no_new_orders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sc, notifier = _scanner_with()

    async def _has_any(inn: str) -> bool:
        return True

    async def _sync(inn: str, orders: list[BlockingOrder]) -> list[BlockingOrder]:
        return []

    monkeypatch.setattr(scanner_module.FnsBlockingRepository, "has_any", _has_any)
    monkeypatch.setattr(scanner_module.FnsBlockingRepository, "sync", _sync)

    await sc._check_and_notify("77", {"rows": []})

    assert notifier.sent == []
