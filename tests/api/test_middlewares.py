"""Тесты OIDC-middleware аутентификации Cloud Tasks."""

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from api import middlewares
from api.middlewares import create_oidc_middleware

AUDIENCE = "https://bot.example.com"
SA_EMAIL = "tasks@project.iam.gserviceaccount.com"


async def _protected(request: web.Request) -> web.Response:
    return web.json_response({"ok": True})


def _make_app(
    audience: str | None = AUDIENCE,
    email: str | None = SA_EMAIL,
) -> web.Application:
    app = web.Application(middlewares=[create_oidc_middleware(audience, email)])
    app.router.add_post("/events/test", _protected)
    app.router.add_get("/health", _protected)
    return app


@pytest_asyncio.fixture
async def client() -> AsyncIterator[TestClient]:
    """Клиент к тестовому приложению с настроенной аутентификацией."""
    async with TestClient(TestServer(_make_app())) as client:
        yield client


async def test_health_bypasses_auth(client: TestClient) -> None:
    """/health доступен без токена."""
    response = await client.get("/health")
    assert response.status == 200


async def test_missing_token_returns_401(client: TestClient) -> None:
    """Запрос без Authorization отклоняется 401."""
    response = await client.post("/events/test")
    assert response.status == 401


async def test_invalid_token_returns_401(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Невалидный токен отклоняется 401."""
    def _raise(token: str, audience: str) -> dict:
        raise ValueError("bad token")

    monkeypatch.setattr(middlewares, "_verify_token", _raise)
    response = await client.post(
        "/events/test", headers={"Authorization": "Bearer bad"}
    )
    assert response.status == 401


async def test_wrong_email_returns_403(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Токен от чужого сервисного аккаунта отклоняется 403."""
    monkeypatch.setattr(
        middlewares,
        "_verify_token",
        lambda token, audience: {"email": "evil@x.com", "email_verified": True},
    )
    response = await client.post(
        "/events/test", headers={"Authorization": "Bearer t"}
    )
    assert response.status == 403


async def test_unverified_email_returns_403(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Токен с неподтверждённым email отклоняется 403."""
    monkeypatch.setattr(
        middlewares,
        "_verify_token",
        lambda token, audience: {"email": SA_EMAIL, "email_verified": False},
    )
    response = await client.post(
        "/events/test", headers={"Authorization": "Bearer t"}
    )
    assert response.status == 403


async def test_valid_token_passes(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Валидный токен от нужного аккаунта пропускается."""
    monkeypatch.setattr(
        middlewares,
        "_verify_token",
        lambda token, audience: {"email": SA_EMAIL, "email_verified": True},
    )
    response = await client.post(
        "/events/test", headers={"Authorization": "Bearer good"}
    )
    assert response.status == 200


async def test_unconfigured_auth_returns_503() -> None:
    """Без настроек auth защищённые пути отвечают 503."""
    async with TestClient(TestServer(_make_app(audience=None))) as client:
        response = await client.post(
            "/events/test", headers={"Authorization": "Bearer t"}
        )
        assert response.status == 503
