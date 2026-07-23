"""Тесты aiohttp-сервера API."""

from unittest.mock import MagicMock

from aiohttp.test_utils import TestClient, TestServer
from api.server import BOT_KEY, create_app


async def test_health_returns_ok() -> None:
    """GET /health отвечает 200 без аутентификации."""
    app = create_app(bot=MagicMock())
    async with TestClient(TestServer(app)) as client:
        response = await client.get("/health")
        assert response.status == 200
        assert await response.json() == {"status": "ok"}


async def test_create_app_stores_bot() -> None:
    """Экземпляр бота доступен обработчикам через BOT_KEY."""
    bot = MagicMock()
    app = create_app(bot=bot)
    assert app[BOT_KEY] is bot
