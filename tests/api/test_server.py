"""Тесты aiohttp-сервера API."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram import Dispatcher
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from api.server import BOT_KEY, create_app
from core.config import config


def _mock_bot() -> MagicMock:
    """Mock-бот с awaitable ``session.close`` (нужно для on_shutdown aiogram)."""
    bot = MagicMock()
    bot.session.close = AsyncMock()
    return bot


def _create_app() -> web.Application:
    """Собирает приложение с реальным диспетчером и mock-ботом."""
    return create_app(bot=_mock_bot(), dp=Dispatcher())


async def test_health_returns_ok() -> None:
    """GET /health отвечает 200 без аутентификации."""
    app = _create_app()
    async with TestClient(TestServer(app)) as client:
        response = await client.get("/health")
        assert response.status == 200
        assert await response.json() == {"status": "ok"}


async def test_create_app_stores_bot() -> None:
    """Экземпляр бота доступен обработчикам через BOT_KEY."""
    bot = _mock_bot()
    app = create_app(bot=bot, dp=Dispatcher())
    assert app[BOT_KEY] is bot


async def test_webhook_route_is_registered() -> None:
    """POST на webhook-путь обрабатывается (не 404)."""
    app = _create_app()
    async with TestClient(TestServer(app)) as client:
        response = await client.post(config.webhook_path, json={})
        assert response.status != 404


async def test_webhook_rejects_wrong_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """Запрос без верного secret token отклоняется с 401."""
    monkeypatch.setattr(config, "webhook_secret", MagicMock(get_secret_value=lambda: "right"))
    app = _create_app()
    async with TestClient(TestServer(app)) as client:
        response = await client.post(
            config.webhook_path,
            json={},
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
        )
        assert response.status == 401
