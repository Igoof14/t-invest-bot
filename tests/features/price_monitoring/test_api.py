"""Тесты HTTP endpoint'а /events/price-alert."""

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest_asyncio
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from api.keys import BOT_KEY
from features.price_monitoring.api import routes


def _anomaly_payload(**overrides: object) -> dict:
    payload = {
        "figi": "BBG000000001",
        "ticker": "RU000A0JX0J2",
        "name": "Тестовая облигация",
        "old_price": 100.0,
        "new_price": 95.0,
        "change_percent": -5.0,
        "alert_type": "drop_critical",
        "account_name": "Брокерский счёт",
    }
    payload.update(overrides)
    return payload


@pytest_asyncio.fixture
async def bot() -> MagicMock:
    """Мок бота с асинхронным send_message."""
    bot = MagicMock()
    bot.send_message = AsyncMock()
    return bot


@pytest_asyncio.fixture
async def client(bot: MagicMock) -> AsyncIterator[TestClient]:
    """HTTP-клиент к приложению только с роутами price_monitoring."""
    app = web.Application()
    app[BOT_KEY] = bot
    app.add_routes(routes)
    async with TestClient(TestServer(app)) as client:
        yield client


async def test_single_anomaly_sends_one_message(
    client: TestClient, bot: MagicMock
) -> None:
    """Одна аномалия — одно обычное сообщение."""
    body = {"telegram_id": 42, "anomalies": [_anomaly_payload()]}
    response = await client.post("/events/price-alert", json=body)
    assert response.status == 200
    assert await response.json() == {"status": "sent"}
    bot.send_message.assert_awaited_once()
    assert bot.send_message.await_args.args[0] == 42


async def test_many_anomalies_send_aggregated_message(
    client: TestClient, bot: MagicMock
) -> None:
    """Три и более аномалий — одно сводное сообщение."""
    body = {
        "telegram_id": 42,
        "anomalies": [
            _anomaly_payload(figi=f"BBG00000000{i}", ticker=f"T{i}") for i in range(3)
        ],
    }
    response = await client.post("/events/price-alert", json=body)
    assert response.status == 200
    bot.send_message.assert_awaited_once()


async def test_invalid_payload_dropped_with_200(
    client: TestClient, bot: MagicMock
) -> None:
    """Невалидный payload подтверждается 200 без отправки (не ретраим)."""
    response = await client.post("/events/price-alert", json={"telegram_id": 42})
    assert response.status == 200
    assert (await response.json())["status"] == "dropped"
    bot.send_message.assert_not_awaited()


async def test_empty_anomalies_dropped(client: TestClient, bot: MagicMock) -> None:
    """Пустой список аномалий — невалидный payload."""
    response = await client.post(
        "/events/price-alert", json={"telegram_id": 42, "anomalies": []}
    )
    assert (await response.json())["status"] == "dropped"
    bot.send_message.assert_not_awaited()


async def test_send_failure_returns_503(client: TestClient, bot: MagicMock) -> None:
    """Ошибка отправки в Telegram — 503, Cloud Tasks сделает ретрай."""
    bot.send_message.side_effect = RuntimeError("telegram down")
    body = {"telegram_id": 42, "anomalies": [_anomaly_payload()]}
    response = await client.post("/events/price-alert", json=body)
    assert response.status == 503
