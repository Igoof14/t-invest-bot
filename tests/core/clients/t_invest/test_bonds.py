"""Тесты клиента купонных выплат T-Invest.

Канал и сервисы подменяются целиком: проверяется отбор операций и раскладка по
счетам, а не транспорт. Отдельно закреплено, что ``AsyncClient`` здесь больше не
используется — вход в него инициализирует Sentry на error hub Т-Банка и
перехватывает Sentry-клиент всего процесса.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from core.clients.t_invest import bonds
from core.clients.t_invest.bonds import get_coupon_payment
from t_tech.invest.schemas import OperationType

START = datetime(2026, 1, 1)


@dataclass
class _Money:
    """Денежная величина в формате SDK: целые и нанокопейки."""

    units: int
    nano: int = 0


def _account(account_id: str, name: str) -> MagicMock:
    account = MagicMock()
    account.id = account_id
    account.name = name
    return account


def _operation(operation_type: OperationType, units: int) -> MagicMock:
    operation = MagicMock()
    operation.operation_type = operation_type
    operation.payment = _Money(units)
    return operation


class _FakeChannel:
    """Заглушка gRPC-канала — асинхронный контекстный менеджер."""

    async def __aenter__(self) -> _FakeChannel:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


def _patch_sdk(
    monkeypatch: pytest.MonkeyPatch,
    accounts: list[MagicMock],
    operations: dict[str, list[MagicMock]],
) -> dict[str, Any]:
    """Подменяет канал и сервисы SDK, запоминая, с чем их позвали."""
    seen: dict[str, Any] = {}

    def _create_channel(**kwargs: Any) -> _FakeChannel:
        seen["channel_kwargs"] = kwargs
        return _FakeChannel()

    def _services(channel: Any, *, token: str) -> MagicMock:
        seen["token"] = token
        client = MagicMock()
        client.users.get_accounts = AsyncMock(return_value=MagicMock(accounts=accounts))

        async def _get_operations(*, account_id: str, from_: datetime) -> MagicMock:
            seen.setdefault("from_", from_)
            return MagicMock(operations=operations.get(account_id, []))

        client.operations.get_operations = _get_operations
        return client

    monkeypatch.setattr(bonds, "create_channel", _create_channel)
    monkeypatch.setattr(bonds, "AsyncServices", _services)
    monkeypatch.setattr(
        bonds.BotUserRepository, "get_token_by_telegram_id", AsyncMock(return_value="t.secret")
    )
    return seen


async def test_sums_only_coupon_operations(monkeypatch: pytest.MonkeyPatch) -> None:
    """Купоны складываются, всё остальное в сумму не попадает."""
    _patch_sdk(
        monkeypatch,
        [_account("acc-1", "Основной")],
        {
            "acc-1": [
                _operation(OperationType.OPERATION_TYPE_COUPON, 100),
                _operation(OperationType.OPERATION_TYPE_BUY, 5000),
                _operation(OperationType.OPERATION_TYPE_COUPON, 50),
            ]
        },
    )

    result = await get_coupon_payment(777, START)

    assert result is not None
    assert result.total_amount == 150
    assert result.accounts == {"Основной": 150}


async def test_splits_payments_by_account(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_sdk(
        monkeypatch,
        [_account("acc-1", "Основной"), _account("acc-2", "ИИС")],
        {
            "acc-1": [_operation(OperationType.OPERATION_TYPE_COUPON, 100)],
            "acc-2": [_operation(OperationType.OPERATION_TYPE_COUPON, 30)],
        },
    )

    result = await get_coupon_payment(777, START)

    assert result is not None
    assert result.accounts == {"Основной": 100, "ИИС": 30}
    assert result.total_amount == 130


async def test_uses_the_user_token_and_requested_period(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _patch_sdk(
        monkeypatch,
        [_account("acc-1", "Основной")],
        {"acc-1": [_operation(OperationType.OPERATION_TYPE_COUPON, 1)]},
    )

    await get_coupon_payment(777, START)

    assert seen["token"] == "t.secret"
    assert seen["from_"] == START
    # Канал строится асинхронным — иначе await по нему не сработает.
    assert seen["channel_kwargs"] == {"force_async": True}


async def test_returns_none_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Нет токена — нет и вопроса к брокеру: это не «выплат не было»."""
    monkeypatch.setattr(
        bonds.BotUserRepository, "get_token_by_telegram_id", AsyncMock(return_value=None)
    )

    assert await get_coupon_payment(777, START) is None


def test_async_client_is_not_used() -> None:
    """AsyncClient инициализирует Sentry на error hub Т-Банка — он здесь не нужен."""
    assert not hasattr(bonds, "AsyncClient")
