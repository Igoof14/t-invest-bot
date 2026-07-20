"""Тесты клиента синхронизации облигаций пользователя."""

from __future__ import annotations

from unittest.mock import MagicMock

import aiohttp
import pytest
from core.clients.bonds_sync.client import sync_user_bonds
from google.auth.exceptions import GoogleAuthError


class _FakeResponse:
    """Заглушка aiohttp-ответа для async-контекста session.post(...)."""

    def __init__(self, status: int = 200) -> None:
        self.status = status

    async def __aenter__(self) -> _FakeResponse:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def raise_for_status(self) -> None:
        if self.status >= 400:
            raise aiohttp.ClientResponseError(MagicMock(), (), status=self.status)


class _FakeSession:
    """Заглушка aiohttp.ClientSession, возвращающая заранее заданный ответ."""

    def __init__(self, response: _FakeResponse) -> None:
        self._response = response

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def post(self, *args: object, **kwargs: object) -> _FakeResponse:
        return self._response


@pytest.fixture(autouse=True)
def _bonds_sync_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "core.clients.bonds_sync.client.config.bonds_sync_url",
        "https://bonds-sync.example.run.app",
    )


async def test_sync_user_bonds_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "core.clients.bonds_sync.client._fetch_id_token", lambda audience: "fake-token"
    )
    monkeypatch.setattr(
        "core.clients.bonds_sync.client.aiohttp.ClientSession",
        lambda *args, **kwargs: _FakeSession(_FakeResponse(200)),
    )

    assert await sync_user_bonds(telegram_id=123) is True


async def test_sync_user_bonds_no_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("core.clients.bonds_sync.client.config.bonds_sync_url", None)

    assert await sync_user_bonds(telegram_id=123) is False


async def test_sync_user_bonds_auth_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(audience: str) -> str:
        raise GoogleAuthError("no metadata server")

    monkeypatch.setattr("core.clients.bonds_sync.client._fetch_id_token", _raise)

    assert await sync_user_bonds(telegram_id=123) is False


async def test_sync_user_bonds_empty_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("core.clients.bonds_sync.client._fetch_id_token", lambda audience: None)

    assert await sync_user_bonds(telegram_id=123) is False


async def test_sync_user_bonds_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "core.clients.bonds_sync.client._fetch_id_token", lambda audience: "fake-token"
    )
    monkeypatch.setattr(
        "core.clients.bonds_sync.client.aiohttp.ClientSession",
        lambda *args, **kwargs: _FakeSession(_FakeResponse(500)),
    )

    assert await sync_user_bonds(telegram_id=123) is False
