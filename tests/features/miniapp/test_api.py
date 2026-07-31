"""Тесты HTTP API мини-аппа."""

from collections.abc import AsyncIterator
from datetime import time
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from core.clients.backend import notifications as notifications_api
from core.clients.backend import users as users_api
from core.clients.backend.errors import BackendError, UserNotFound
from core.clients.backend.notifications import (
    DisclosureAlertSettings,
    NotificationSettings,
    OfferAlertSettings,
    PriceAlertSettings,
)
from core.clients.backend.users import Registration
from core.config import config
from features.miniapp import api as miniapp_api
from features.miniapp.middlewares import auth_middleware, no_store_middleware
from pydantic import SecretStr

from .test_auth import BOT_TOKEN, make_init_data

TELEGRAM_ID = 42


def _settings() -> NotificationSettings:
    return NotificationSettings(
        offers=OfferAlertSettings(
            alerts_enabled=True,
            first_alert=20,
            second_alert=7,
            notification_time=time(9, 30),
        ),
        prices=PriceAlertSettings(alerts_enabled=True),
        fns_enabled=False,
        enabled_agencies=frozenset({"nra"}),
        disclosure=DisclosureAlertSettings(alerts_enabled=True, min_risk_level="high"),
    )


@pytest.fixture(autouse=True)
def bot_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Токен, которым подписаны тестовые initData."""
    monkeypatch.setattr(config, "bot_token", SecretStr(BOT_TOKEN))
    monkeypatch.setattr(config, "miniapp_dev_telegram_id", None)


@pytest_asyncio.fixture
async def client() -> AsyncIterator[TestClient]:
    """Клиент к приложению с аутентификацией и роутами мини-аппа."""
    app = web.Application(middlewares=[no_store_middleware, auth_middleware])
    app.add_routes(miniapp_api.routes)
    async with TestClient(TestServer(app)) as client:
        yield client


def auth() -> dict[str, str]:
    """Заголовок с подписанной initData."""
    return {"Authorization": f"tma {make_init_data()}"}


async def test_request_without_init_data_rejected(client: TestClient) -> None:
    """Без подписи API недоступен — иначе можно читать чужие настройки."""
    response = await client.get("/miniapp/api/notifications")
    assert response.status == 401


async def test_request_with_forged_init_data_rejected(client: TestClient) -> None:
    """Подделанная подпись отклоняется."""
    forged = make_init_data(corrupt_hash=True)
    response = await client.get(
        "/miniapp/api/notifications", headers={"Authorization": f"tma {forged}"}
    )
    assert response.status == 401


async def test_dev_mode_allows_request_without_signature(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """В дев-режиме запрос без подписи считается запросом заданного юзера."""
    monkeypatch.setattr(config, "miniapp_dev_telegram_id", 777)
    get_settings = AsyncMock(return_value=_settings())
    monkeypatch.setattr(notifications_api, "get_settings", get_settings)

    response = await client.get("/miniapp/api/notifications")

    assert response.status == 200
    get_settings.assert_awaited_once_with(777)


async def test_notifications_returns_all_sections(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Все пять разделов приходят одним ответом."""
    monkeypatch.setattr(
        notifications_api, "get_settings", AsyncMock(return_value=_settings())
    )

    response = await client.get("/miniapp/api/notifications", headers=auth())

    assert response.status == 200
    payload = await response.json()
    assert payload["offers"] == {
        "alerts_enabled": True,
        "first_alert": 20,
        "second_alert": 7,
        "notification_time": "09:30:00",
    }
    assert payload["ratings"] == {"enabled_agencies": ["nra"]}
    assert payload["fns"] == {"alerts_enabled": False}
    assert payload["disclosure"]["min_risk_level"] == "high"
    assert set(payload) == {"offers", "prices", "ratings", "fns", "disclosure"}


async def test_toggle_uses_id_from_signature(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """telegram_id берётся из подписи, а не из тела запроса."""
    toggle = AsyncMock(return_value=True)
    monkeypatch.setattr(notifications_api, "toggle", toggle)

    response = await client.post(
        "/miniapp/api/notifications/offers/toggle",
        headers=auth(),
        json={"telegram_id": 999},
    )

    assert response.status == 200
    assert await response.json() == {"alerts_enabled": True}
    toggle.assert_awaited_once_with(TELEGRAM_ID, "offers")


async def test_unknown_section_returns_404(client: TestClient) -> None:
    """Раздела нет — до бэкенда запрос не доходит."""
    response = await client.post(
        "/miniapp/api/notifications/whatever/toggle", headers=auth()
    )
    assert response.status == 404


async def test_unknown_agency_returns_404(client: TestClient) -> None:
    """Неизвестный код агентства в бэкенд не пропускается."""
    response = await client.post(
        "/miniapp/api/notifications/ratings/unknown/toggle", headers=auth()
    )
    assert response.status == 404


async def test_toggle_known_agency(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Известное агентство переключается."""
    toggle = AsyncMock(return_value=True)
    monkeypatch.setattr(notifications_api, "toggle_agency", toggle)

    response = await client.post(
        "/miniapp/api/notifications/ratings/nra/toggle", headers=auth()
    )

    assert response.status == 200
    toggle.assert_awaited_once_with(TELEGRAM_ID, "nra")


async def test_agencies_listed_from_enum(client: TestClient) -> None:
    """Список агентств отдаёт сервер — фронтенду его хардкодить не нужно."""
    response = await client.get("/miniapp/api/ratings/agencies", headers=auth())

    assert response.status == 200
    assert {"code": "nra", "name": "НРА"} in await response.json()


async def test_update_offers_passes_only_sent_fields(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PATCH частичный: не присланные поля не трогаются."""
    update = AsyncMock(return_value=_settings().offers)
    monkeypatch.setattr(notifications_api, "update_offers", update)

    response = await client.patch(
        "/miniapp/api/notifications/offers", headers=auth(), json={"first_alert": 20}
    )

    assert response.status == 200
    update.assert_awaited_once_with(TELEGRAM_ID, first_alert=20)


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/miniapp/api/notifications/offers", {"first_alert": 0}),
        ("/miniapp/api/notifications/offers", {"second_alert": 400}),
        ("/miniapp/api/notifications/prices", {"drop_warning_threshold": 0}),
        ("/miniapp/api/notifications/prices", {"rise_critical_threshold": 100}),
        ("/miniapp/api/notifications/disclosure", {"min_risk_level": "extreme"}),
    ],
)
async def test_out_of_range_values_rejected(
    client: TestClient, path: str, body: dict
) -> None:
    """Значения вне допустимого диапазона до бэкенда не доходят."""
    response = await client.patch(path, headers=auth(), json=body)
    assert response.status == 400


async def test_backend_failure_returns_502(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Недоступный бэкенд — 502, а не 500 с деталями приватного сервиса."""
    monkeypatch.setattr(
        notifications_api,
        "get_settings",
        AsyncMock(side_effect=BackendError("connection refused")),
    )

    response = await client.get("/miniapp/api/notifications", headers=auth())

    assert response.status == 502
    assert "connection refused" not in (await response.text())


async def test_unknown_user_returns_404(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Бэкенд не знает пользователя — 404."""
    monkeypatch.setattr(
        notifications_api, "get_settings", AsyncMock(side_effect=UserNotFound("нет такого"))
    )

    response = await client.get("/miniapp/api/notifications", headers=auth())

    assert response.status == 404


async def test_me_registers_user(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """/me регистрирует открывшего мини-апп: он мог не нажимать /start."""
    register = AsyncMock(return_value=Registration(is_new_user=True, has_token=False))
    monkeypatch.setattr(users_api, "register", register)

    response = await client.get("/miniapp/api/me", headers=auth())

    assert response.status == 200
    payload = await response.json()
    assert payload == {
        "telegram_id": TELEGRAM_ID,
        "first_name": "Иван",
        "last_name": None,
        "username": "ivan",
        "has_token": False,
    }
    register.assert_awaited_once_with(
        TELEGRAM_ID, username="ivan", first_name="Иван", last_name=None
    )


async def test_set_and_delete_token(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Токен подключается и отключается для пользователя из подписи."""
    set_token = AsyncMock()
    delete_token = AsyncMock()
    monkeypatch.setattr(users_api, "set_token", set_token)
    monkeypatch.setattr(users_api, "delete_token", delete_token)

    saved = await client.put(
        "/miniapp/api/token", headers=auth(), json={"token": "t.secret"}
    )
    removed = await client.delete("/miniapp/api/token", headers=auth())

    assert (saved.status, await saved.json()) == (200, {"has_token": True})
    assert (removed.status, await removed.json()) == (200, {"has_token": False})
    set_token.assert_awaited_once_with(TELEGRAM_ID, "t.secret")
    delete_token.assert_awaited_once_with(TELEGRAM_ID)


async def test_empty_token_rejected(client: TestClient) -> None:
    """Пустой токен не сохраняется."""
    response = await client.put("/miniapp/api/token", headers=auth(), json={"token": ""})
    assert response.status == 400


async def test_responses_are_not_cacheable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ответы API не кэшируются: они зависят от того, кто спрашивает."""
    monkeypatch.setattr(
        notifications_api, "get_settings", AsyncMock(return_value=_settings())
    )

    response = await client.get("/miniapp/api/notifications", headers=auth())

    assert response.headers["Cache-Control"] == "no-store"


async def test_rejections_are_not_cacheable(client: TestClient) -> None:
    """Отказ тоже не кэшируется — иначе он переживёт выкатку исправления."""
    unauthorized = await client.get("/miniapp/api/notifications")
    not_found = await client.post(
        "/miniapp/api/notifications/whatever/toggle", headers=auth()
    )
    bad_request = await client.patch(
        "/miniapp/api/notifications/offers", headers=auth(), json={"first_alert": 0}
    )

    assert unauthorized.status == 401
    assert not_found.status == 404
    assert bad_request.status == 400
    for response in (unauthorized, not_found, bad_request):
        assert response.headers["Cache-Control"] == "no-store"
