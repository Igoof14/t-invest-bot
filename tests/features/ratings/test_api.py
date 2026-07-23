"""Тесты HTTP endpoint'а /events/rating-change."""

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest_asyncio
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from api.keys import BOT_KEY
from features.ratings.api import routes


def _change_payload() -> dict:
    return {
        "event": {
            "entity_name": "ООО Тест",
            "url": "https://example.com/rating/1",
            "rating_action": "Понижен",
            "rating_value": "BB+.ru",
            "outlook": "Негативный",
        },
        "matched_bond_names": [{"isin": "RU000A108EF8", "name": "Тест-облигация"}],
    }


@pytest_asyncio.fixture
async def bot() -> MagicMock:
    """Мок бота с асинхронным send_message."""
    bot = MagicMock()
    bot.send_message = AsyncMock()
    return bot


@pytest_asyncio.fixture
async def client(bot: MagicMock) -> AsyncIterator[TestClient]:
    """HTTP-клиент к приложению только с роутами ratings."""
    app = web.Application()
    app[BOT_KEY] = bot
    app.add_routes(routes)
    async with TestClient(TestServer(app)) as client:
        yield client


async def test_changes_send_one_message(client: TestClient, bot: MagicMock) -> None:
    """Событие с изменениями рейтинга — одно сообщение пользователю."""
    body = {"telegram_id": 42, "alerts": [_change_payload()]}
    response = await client.post("/events/rating-change", json=body)
    assert response.status == 200
    assert await response.json() == {"status": "sent"}
    bot.send_message.assert_awaited_once()
    message_text = bot.send_message.await_args.args[1]
    assert "Тест-облигация" in message_text
    assert "RU000A108EF8" in message_text


async def test_invalid_payload_dropped_with_200(
    client: TestClient, bot: MagicMock
) -> None:
    """Невалидный payload подтверждается 200 без отправки."""
    response = await client.post("/events/rating-change", json={"telegram_id": 42})
    assert (await response.json())["status"] == "dropped"
    bot.send_message.assert_not_awaited()


async def test_send_failure_returns_503(client: TestClient, bot: MagicMock) -> None:
    """Ошибка отправки в Telegram — 503, Cloud Tasks сделает ретрай."""
    bot.send_message.side_effect = RuntimeError("telegram down")
    body = {"telegram_id": 42, "alerts": [_change_payload()]}
    response = await client.post("/events/rating-change", json=body)
    assert response.status == 503
