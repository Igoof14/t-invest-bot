"""Тесты OIDC-авторизации вызовов бэкенда."""

from __future__ import annotations

import time

import pytest
from core.clients.backend import auth
from core.clients.backend.errors import BackendAuthError
from google.auth.exceptions import GoogleAuthError

AUDIENCE = "https://backend.example.run.app"


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    auth.reset_token_cache()


def _stub_fetch(monkeypatch: pytest.MonkeyPatch, tokens: list[str | None]) -> list[str]:
    """Подменяет получение токена, возвращая элементы `tokens` по очереди."""
    calls: list[str] = []

    def _fetch(audience: str) -> str | None:
        calls.append(audience)
        return tokens[min(len(calls) - 1, len(tokens) - 1)]

    monkeypatch.setattr(auth, "_fetch_id_token", _fetch)
    return calls


async def test_token_is_cached_between_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _stub_fetch(monkeypatch, ["first", "second"])
    monkeypatch.setattr(auth, "_expires_at", lambda token: time.time() + 3600)

    assert await auth.get_id_token(AUDIENCE) == "first"
    assert await auth.get_id_token(AUDIENCE) == "first"
    assert calls == [AUDIENCE]


async def test_token_is_refreshed_before_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _stub_fetch(monkeypatch, ["first", "second"])
    # Срок истекает раньше, чем через _REFRESH_MARGIN — токен считаем протухшим.
    monkeypatch.setattr(auth, "_expires_at", lambda token: time.time() + 60)

    assert await auth.get_id_token(AUDIENCE) == "first"
    assert await auth.get_id_token(AUDIENCE) == "second"
    assert len(calls) == 2


async def test_auth_error_raised_on_google_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(audience: str) -> str:
        raise GoogleAuthError("no credentials")

    monkeypatch.setattr(auth, "_fetch_id_token", _raise)

    with pytest.raises(BackendAuthError, match="application-default login"):
        await auth.get_id_token(AUDIENCE)


async def test_auth_error_raised_on_empty_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_fetch(monkeypatch, [None])

    with pytest.raises(BackendAuthError):
        await auth.get_id_token(AUDIENCE)


async def test_auth_headers_contain_bearer(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_fetch(monkeypatch, ["tok"])
    monkeypatch.setattr(auth, "_expires_at", lambda token: time.time() + 3600)

    assert await auth.auth_headers(AUDIENCE) == {"Authorization": "Bearer tok"}
