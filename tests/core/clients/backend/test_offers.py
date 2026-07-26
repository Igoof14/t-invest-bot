"""Тесты клиента оферт бэкенда."""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import MagicMock

import aiohttp
import pytest
from core.clients.backend.errors import BackendError, BackendNotConfigured, UserNotFound
from core.clients.backend.offers import get_offers

BASE_URL = "https://backend.example.run.app"

PAYLOAD: dict[str, Any] = {
    "telegram_id": 1825344258,
    "items": [
        {
            "bond": {
                "secid": "RU000A10AS28",
                "isin": "RU000A10AS28",
                "shortname": "БинФарм1P4",
                "name": "Биннофарм Групп 001Р-04",
                "facevalue": "1000",
                "faceunit": "SUR",
                "matdate": "2028-01-22",
            },
            "offer": {
                "date": "2026-08-05",
                "type": "Оферта",
                "date_start": "2026-07-27",
                "date_end": "2026-07-31",
                "price": "100",
                "value": "1000",
                "agent": None,
                "days_left": 10,
            },
            "quantity": "44.0000",
            "accounts": [
                {
                    "broker": "tbank",
                    "account_id": "2045796893",
                    "account_name": "ИИСус",
                    "quantity": "30.0000",
                },
                {
                    "broker": "tbank",
                    "account_id": "2046032553",
                    "account_name": "Брокерский счет",
                    "quantity": "14.0000",
                },
            ],
        }
    ],
}


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


@pytest.fixture(autouse=True)
def _backend_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("core.clients.backend.offers.config.backend_url", BASE_URL)
    monkeypatch.setattr(
        "core.clients.backend.offers.auth_headers",
        _fake_auth_headers,
    )
    _FakeSession.last_call = {}


async def _fake_auth_headers(audience: str) -> dict[str, str]:
    return {"Authorization": f"Bearer token-for-{audience}"}


def _patch_session(monkeypatch: pytest.MonkeyPatch, response: _FakeResponse) -> None:
    monkeypatch.setattr(
        "core.clients.backend.offers.aiohttp.ClientSession",
        lambda *args, **kwargs: _FakeSession(response),
    )


async def test_parses_response(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_session(monkeypatch, _FakeResponse(200, PAYLOAD))

    offers = await get_offers(telegram_id=1825344258, limit=5)

    assert len(offers) == 1
    item = offers[0]
    assert item.secid == "RU000A10AS28"
    assert item.facevalue == 1000.0
    assert item.quantity == 44.0
    assert item.offer_date == date(2026, 8, 5)
    assert item.maturity_date == date(2028, 1, 22)
    assert item.days_left == 10
    assert [acc.account_name for acc in item.accounts] == ["ИИСус", "Брокерский счет"]
    assert item.accounts[1].quantity == 14.0


async def test_request_url_params_and_auth_header(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_session(monkeypatch, _FakeResponse(200, PAYLOAD))

    await get_offers(telegram_id=42, limit=5)

    assert _FakeSession.last_call["url"] == f"{BASE_URL}/api/v1/users/42/offers"
    assert _FakeSession.last_call["params"] == {"limit": 5}
    assert _FakeSession.last_call["headers"] == {"Authorization": f"Bearer token-for-{BASE_URL}"}


@pytest.mark.parametrize(("limit", "expected"), [(0, 1), (100, 50), (7, 7)])
async def test_limit_is_clamped(monkeypatch: pytest.MonkeyPatch, limit: int, expected: int) -> None:
    _patch_session(monkeypatch, _FakeResponse(200, PAYLOAD))

    await get_offers(telegram_id=42, limit=limit)

    assert _FakeSession.last_call["params"] == {"limit": expected}


async def test_empty_items_returns_empty_list(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_session(monkeypatch, _FakeResponse(200, {"telegram_id": 42, "items": []}))

    assert await get_offers(telegram_id=42) == []


async def test_unknown_user_raises_user_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_session(monkeypatch, _FakeResponse(404, {"detail": "no", "code": "not_found"}))

    with pytest.raises(UserNotFound):
        await get_offers(telegram_id=42)


async def test_server_error_raises_backend_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_session(monkeypatch, _FakeResponse(500))

    with pytest.raises(BackendError):
        await get_offers(telegram_id=42)


async def test_missing_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("core.clients.backend.offers.config.backend_url", None)

    with pytest.raises(BackendNotConfigured):
        await get_offers(telegram_id=42)
