"""Тесты HTTP endpoint'а /events/fns-block."""

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from aiogram.exceptions import TelegramForbiddenError
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from api.keys import BOT_KEY
from features.fns_monitoring.api import routes


def _alert_payload() -> dict:
    return {
        "inn": "7700000000",
        "entity_name": "ООО Тест",
        "orders": [{"inn": "7700000000", "block_uid": "044525225:123"}],
        "matched_bonds": [{"name": "Тест-облигация", "ticker": "TST01"}],
    }


@pytest_asyncio.fixture
async def bot() -> MagicMock:
    """Мок бота с асинхронным send_message."""
    bot = MagicMock()
    bot.send_message = AsyncMock()
    return bot


@pytest_asyncio.fixture
async def client(bot: MagicMock) -> AsyncIterator[TestClient]:
    """HTTP-клиент к приложению только с роутами fns_monitoring."""
    app = web.Application()
    app[BOT_KEY] = bot
    app.add_routes(routes)
    async with TestClient(TestServer(app)) as client:
        yield client


async def test_alerts_send_one_message(client: TestClient, bot: MagicMock) -> None:
    """Событие с блокировками — одно сообщение пользователю."""
    body = {"telegram_id": 42, "alerts": [_alert_payload()]}
    response = await client.post("/events/fns-block", json=body)
    assert response.status == 200
    assert await response.json() == {"status": "sent"}
    bot.send_message.assert_awaited_once()
    assert bot.send_message.await_args.args[0] == 42


async def test_invalid_payload_dropped_with_200(
    client: TestClient, bot: MagicMock
) -> None:
    """Невалидный payload подтверждается 200 без отправки."""
    response = await client.post("/events/fns-block", json={"telegram_id": 42})
    assert response.status == 200
    assert (await response.json())["status"] == "dropped"
    bot.send_message.assert_not_awaited()


async def test_send_failure_returns_503(client: TestClient, bot: MagicMock) -> None:
    """Ошибка отправки в Telegram — 503, Cloud Tasks сделает ретрай."""
    bot.send_message.side_effect = RuntimeError("telegram down")
    body = {"telegram_id": 42, "alerts": [_alert_payload()]}
    response = await client.post("/events/fns-block", json=body)
    assert response.status == 503


async def test_blocked_user_dropped_with_200(
    client: TestClient, bot: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Заблокировавший бота пользователь: 200 dropped, а не бесконечный ретрай."""
    deactivate = AsyncMock(return_value=True)
    monkeypatch.setattr(
        "features.users.repository.BotUserRepository.deactivate_user", deactivate
    )
    bot.send_message.side_effect = TelegramForbiddenError(method=None, message="blocked")

    body = {"telegram_id": 42, "alerts": [_alert_payload()]}
    response = await client.post("/events/fns-block", json=body)

    assert response.status == 200
    assert (await response.json())["status"] == "dropped"
    deactivate.assert_awaited_once_with(42)
