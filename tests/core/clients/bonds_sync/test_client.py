"""Тесты клиента синхронизации портфеля пользователя."""

from __future__ import annotations

from unittest.mock import MagicMock

import aiohttp
import pytest
from core.clients.bonds_sync.client import sync_user_bonds, sync_user_events
from google.auth.exceptions import GoogleAuthError


class _FakeResponse:
    """Заглушка aiohttp-ответа для async-контекста session.post(...)."""

    def __init__(self, status: int = 200, payload: dict | None = None) -> None:
        self.status = status
        self._payload = {"telegram_id": 123, "bonds_synced": 7} if payload is None else payload

    async def __aenter__(self) -> _FakeResponse:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def raise_for_status(self) -> None:
        if self.status >= 400:
            raise aiohttp.ClientResponseError(MagicMock(), (), status=self.status)

    async def json(self) -> dict:
        return self._payload


class _FakeSession:
    """Заглушка aiohttp.ClientSession, возвращающая заранее заданный ответ."""

    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        # URL'ы запросов: по ним тесты проверяют, какой эндпоинт был дёрнут.
        self.urls: list[str] = []

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def post(self, url: str, *args: object, **kwargs: object) -> _FakeResponse:
        self.urls.append(url)
        return self._response


@pytest.fixture(autouse=True)
def _bonds_sync_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "core.clients.bonds_sync.client.config.bonds_sync_url",
        "https://bonds-sync.example.run.app",
    )


def _patch_session(monkeypatch: pytest.MonkeyPatch, response: _FakeResponse) -> _FakeSession:
    """Подменяет токен и сессию, возвращая заглушку для проверки URL."""
    monkeypatch.setattr(
        "core.clients.bonds_sync.client._fetch_id_token", lambda audience: "fake-token"
    )
    session = _FakeSession(response)
    monkeypatch.setattr(
        "core.clients.bonds_sync.client.aiohttp.ClientSession",
        lambda *args, **kwargs: session,
    )
    return session


async def test_sync_user_bonds_success(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _patch_session(monkeypatch, _FakeResponse(200))

    assert await sync_user_bonds(telegram_id=123) == 7
    assert session.urls == ["https://bonds-sync.example.run.app/sync/123"]


async def test_sync_user_events_success(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _patch_session(
        monkeypatch, _FakeResponse(200, {"telegram_id": 123, "events_synced": 42})
    )

    assert await sync_user_events(telegram_id=123) == 42
    assert session.urls == ["https://bonds-sync.example.run.app/sync/events/123"]


async def test_sync_user_events_without_count_in_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ответ облигаций не годится для операций: ждём именно events_synced."""
    _patch_session(monkeypatch, _FakeResponse(200, {"telegram_id": 123, "bonds_synced": 7}))

    assert await sync_user_events(telegram_id=123) is None


async def test_sync_user_events_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_session(monkeypatch, _FakeResponse(500))

    assert await sync_user_events(telegram_id=123) is None


async def test_sync_user_events_no_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("core.clients.bonds_sync.client.config.bonds_sync_url", None)

    assert await sync_user_events(telegram_id=123) is None


async def test_sync_user_bonds_without_count_in_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "core.clients.bonds_sync.client._fetch_id_token", lambda audience: "fake-token"
    )
    monkeypatch.setattr(
        "core.clients.bonds_sync.client.aiohttp.ClientSession",
        lambda *args, **kwargs: _FakeSession(_FakeResponse(200, {"telegram_id": 123})),
    )

    assert await sync_user_bonds(telegram_id=123) is None


async def test_sync_user_bonds_no_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("core.clients.bonds_sync.client.config.bonds_sync_url", None)

    assert await sync_user_bonds(telegram_id=123) is None


async def test_sync_user_bonds_auth_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(audience: str) -> str:
        raise GoogleAuthError("no metadata server")

    monkeypatch.setattr("core.clients.bonds_sync.client._fetch_id_token", _raise)

    assert await sync_user_bonds(telegram_id=123) is None


async def test_sync_user_bonds_empty_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("core.clients.bonds_sync.client._fetch_id_token", lambda audience: None)

    assert await sync_user_bonds(telegram_id=123) is None


async def test_sync_user_bonds_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "core.clients.bonds_sync.client._fetch_id_token", lambda audience: "fake-token"
    )
    monkeypatch.setattr(
        "core.clients.bonds_sync.client.aiohttp.ClientSession",
        lambda *args, **kwargs: _FakeSession(_FakeResponse(500)),
    )

    assert await sync_user_bonds(telegram_id=123) is None
