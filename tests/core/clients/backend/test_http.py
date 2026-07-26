"""Тесты HTTP-обвязки запросов к бэкенду."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import aiohttp
import pytest
from core.clients.backend.errors import BackendError, BackendNotConfigured, UserNotFound
from core.clients.backend.http import fetch_user_items

BASE_URL = "https://backend.example.run.app"


class _FakeResponse:
    """Заглушка aiohttp-ответа для async-контекста session.get(...)."""

    def __init__(self, status: int = 200, payload: dict[str, Any] | None = None) -> None:
        self.status = status
        self._payload = payload or {}

    async def __aenter__(self) -> _FakeResponse:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def raise_for_status(self) -> None:
        if self.status >= 400:
            raise aiohttp.ClientResponseError(MagicMock(), (), status=self.status)

    async def json(self) -> dict[str, Any]:
        return self._payload


class _FakeSession:
    """Заглушка aiohttp.ClientSession, запоминающая параметры запроса."""

    last_call: dict[str, Any] = {}

    def __init__(self, response: _FakeResponse) -> None:
        self._response = response

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def get(self, url: str, **kwargs: Any) -> _FakeResponse:
        _FakeSession.last_call = {"url": url, **kwargs}
        return self._response


async def _fake_auth_headers(audience: str) -> dict[str, str]:
    return {"Authorization": f"Bearer token-for-{audience}"}


@pytest.fixture(autouse=True)
def _backend_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("core.clients.backend.http.config.backend_url", BASE_URL)
    monkeypatch.setattr("core.clients.backend.http.auth_headers", _fake_auth_headers)
    _FakeSession.last_call = {}


def patch_session(monkeypatch: pytest.MonkeyPatch, response: _FakeResponse) -> None:
    """Подменяет aiohttp-сессию заранее заданным ответом."""
    monkeypatch.setattr(
        "core.clients.backend.http.aiohttp.ClientSession",
        lambda *args, **kwargs: _FakeSession(response),
    )


async def test_url_params_and_auth_header(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_session(monkeypatch, _FakeResponse(200, {"items": []}))

    await fetch_user_items("offers", telegram_id=42, limit=5)

    assert _FakeSession.last_call["url"] == f"{BASE_URL}/api/v1/users/42/offers"
    assert _FakeSession.last_call["params"] == {"limit": 5}
    assert _FakeSession.last_call["headers"] == {"Authorization": f"Bearer token-for-{BASE_URL}"}


async def test_resource_is_part_of_path(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_session(monkeypatch, _FakeResponse(200, {"items": []}))

    await fetch_user_items("maturities", telegram_id=42, limit=5)

    assert _FakeSession.last_call["url"] == f"{BASE_URL}/api/v1/users/42/maturities"


@pytest.mark.parametrize(("limit", "expected"), [(0, 1), (100, 50), (7, 7)])
async def test_limit_is_clamped(monkeypatch: pytest.MonkeyPatch, limit: int, expected: int) -> None:
    patch_session(monkeypatch, _FakeResponse(200, {"items": []}))

    await fetch_user_items("offers", telegram_id=42, limit=limit)

    assert _FakeSession.last_call["params"] == {"limit": expected}


async def test_missing_items_returns_empty_list(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_session(monkeypatch, _FakeResponse(200, {"telegram_id": 42}))

    assert await fetch_user_items("offers", telegram_id=42, limit=5) == []


async def test_unknown_user_raises_user_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_session(monkeypatch, _FakeResponse(404, {"detail": "no", "code": "not_found"}))

    with pytest.raises(UserNotFound):
        await fetch_user_items("offers", telegram_id=42, limit=5)


async def test_server_error_raises_backend_error(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_session(monkeypatch, _FakeResponse(500))

    with pytest.raises(BackendError):
        await fetch_user_items("offers", telegram_id=42, limit=5)


async def test_missing_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("core.clients.backend.http.config.backend_url", None)

    with pytest.raises(BackendNotConfigured):
        await fetch_user_items("offers", telegram_id=42, limit=5)
