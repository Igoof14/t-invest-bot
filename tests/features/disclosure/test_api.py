"""Тесты HTTP endpoint'а /events/disclosure."""

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from aiogram.exceptions import TelegramForbiddenError
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from api.keys import BOT_KEY
from features.disclosure.api import routes


def _alert_payload(**overrides: object) -> dict:
    payload = {
        "alert_key": "msg-1",
        "source_type": "circumstance",
        "signal_type": "bankruptcy_filing",
        "risk_level": "high",
        "issuer_name": "ООО Тест",
        "issuer_inn": "7701234567",
        "summary": "Подано заявление о признании эмитента банкротом",
        "event_date": "2026-07-20",
        "matched_bonds": [{"isin": "RU000A108EF8", "name": "Тест-облигация"}],
        "circumstance_type": "bankruptcy_filing",
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
    """HTTP-клиент к приложению только с роутами disclosure."""
    app = web.Application()
    app[BOT_KEY] = bot
    app.add_routes(routes)
    async with TestClient(TestServer(app)) as client:
        yield client


async def test_alert_sends_one_message(client: TestClient, bot: MagicMock) -> None:
    """Событие с раскрытием — одно сообщение пользователю."""
    body = {"telegram_id": 42, "alerts": [_alert_payload()]}

    response = await client.post("/events/disclosure", json=body)

    assert response.status == 200
    assert await response.json() == {"status": "sent"}
    bot.send_message.assert_awaited_once()
    message_text = bot.send_message.await_args.args[1]
    assert "ООО Тест" in message_text
    assert "Заявление о банкротстве" in message_text
    assert "RU000A108EF8" in message_text


async def test_market_scope_explains_itself(client: TestClient, bot: MagicMock) -> None:
    """Пользователю без токена сообщение подписывается как рыночное."""
    body = {"telegram_id": 42, "scope": "market", "alerts": [_alert_payload()]}

    await client.post("/events/disclosure", json=body)

    message_text = bot.send_message.await_args.args[1]
    assert "Событие по всему рынку" in message_text


async def test_non_fulfillment_alert_shows_amount(
    client: TestClient, bot: MagicMock
) -> None:
    """Неисполнение обязательств: вид обязательства, тип дефолта и сумма."""
    alert = _alert_payload(
        source_type="default",
        signal_type="coupon",
        circumstance_type=None,
        obligation_type="coupon",
        default_kind="technical",
        unfulfilled_amount=12500000.0,
        risk_level="critical",
    )

    await client.post("/events/disclosure", json={"telegram_id": 42, "alerts": [alert]})

    message_text = bot.send_message.await_args.args[1]
    assert "Выплата купона — технический дефолт" in message_text
    assert "12" in message_text and "500" in message_text


async def test_invalid_payload_dropped_with_200(
    client: TestClient, bot: MagicMock
) -> None:
    """Невалидный payload подтверждается 200 без отправки."""
    response = await client.post("/events/disclosure", json={"telegram_id": 42})

    assert (await response.json())["status"] == "dropped"
    bot.send_message.assert_not_awaited()


async def test_unknown_risk_level_dropped_with_200(
    client: TestClient, bot: MagicMock
) -> None:
    """Уровень вне шкалы — дефект продюсера, ретрай его не исправит."""
    body = {"telegram_id": 42, "alerts": [_alert_payload(risk_level="apocalypse")]}

    response = await client.post("/events/disclosure", json=body)

    assert (await response.json())["status"] == "dropped"
    bot.send_message.assert_not_awaited()


async def test_send_failure_returns_503(client: TestClient, bot: MagicMock) -> None:
    """Ошибка отправки в Telegram — 503, Cloud Tasks сделает ретрай."""
    bot.send_message.side_effect = RuntimeError("telegram down")
    body = {"telegram_id": 42, "alerts": [_alert_payload()]}

    response = await client.post("/events/disclosure", json=body)

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
    response = await client.post("/events/disclosure", json=body)

    assert response.status == 200
    assert (await response.json())["status"] == "dropped"
    deactivate.assert_awaited_once_with(42)
