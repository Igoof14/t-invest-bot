"""Тесты клиента бэкенда для настроек уведомлений."""

from __future__ import annotations

from datetime import time
from unittest.mock import AsyncMock

import pytest
from core.clients.backend import notifications


@pytest.fixture
def request_mock(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Подменяет HTTP-обвязку, оставляя проверку метода, пути и тела."""
    mock = AsyncMock(return_value={})
    monkeypatch.setattr("core.clients.backend.notifications.request", mock)
    return mock


def path_of(request_mock: AsyncMock) -> tuple[str, str]:
    await_args = request_mock.await_args
    assert await_args is not None
    return await_args.args


async def test_get_settings_parses_every_section(request_mock: AsyncMock) -> None:
    request_mock.return_value = {
        "offers": {
            "alerts_enabled": True,
            "first_alert": 20,
            "second_alert": 7,
            "notification_time": "09:30:00",
        },
        "prices": {"alerts_enabled": True, "drop_critical_threshold": 8.5},
        "ratings": {"enabled_agencies": ["nra"]},
        "fns": {"alerts_enabled": True},
    }

    settings = await notifications.get_settings(42)

    assert path_of(request_mock) == ("GET", "/api/v1/users/42/notifications")
    assert settings.offers.first_alert == 20
    assert settings.offers.notification_time == time(9, 30)
    assert settings.prices.drop_critical_threshold == 8.5
    assert settings.enabled_agencies == frozenset({"nra"})
    assert settings.fns_enabled is True


async def test_get_settings_falls_back_to_defaults(request_mock: AsyncMock) -> None:
    """Пустой ответ не должен ронять экран — читается как «всё выключено»."""
    settings = await notifications.get_settings(42)

    assert settings.offers.alerts_enabled is False
    assert settings.offers.first_alert == 14
    assert settings.prices.rise_critical_threshold == 7.0
    assert settings.enabled_agencies == frozenset()
    assert settings.fns_enabled is False


async def test_unparsable_time_falls_back(request_mock: AsyncMock) -> None:
    request_mock.return_value = {"offers": {"notification_time": "нет"}}

    settings = await notifications.get_settings(42)

    assert settings.offers.notification_time == time(10, 0)


@pytest.mark.parametrize("section", ["offers", "prices", "fns"])
async def test_toggle_section(request_mock: AsyncMock, section: str) -> None:
    request_mock.return_value = {"alerts_enabled": True}

    assert await notifications.toggle(42, section) is True
    assert path_of(request_mock) == ("POST", f"/api/v1/users/42/notifications/{section}/toggle")


async def test_toggle_agency(request_mock: AsyncMock) -> None:
    request_mock.return_value = {"alerts_enabled": False}

    assert await notifications.toggle_agency(42, "nkr") is False
    assert path_of(request_mock) == ("POST", "/api/v1/users/42/notifications/ratings/nkr/toggle")


async def test_update_offers_serialises_time(request_mock: AsyncMock) -> None:
    request_mock.return_value = {"alerts_enabled": True, "notification_time": "08:15:00"}

    result = await notifications.update_offers(42, notification_time=time(8, 15))

    await_args = request_mock.await_args
    assert await_args is not None
    assert await_args.args == ("PATCH", "/api/v1/users/42/notifications/offers")
    # time не сериализуется в JSON сам по себе.
    assert await_args.kwargs["json"] == {"notification_time": "08:15:00"}
    assert result.notification_time == time(8, 15)


async def test_update_prices_sends_only_given_fields(request_mock: AsyncMock) -> None:
    await notifications.update_prices(42, drop_warning_threshold=1.5)

    await_args = request_mock.await_args
    assert await_args is not None
    assert await_args.args == ("PATCH", "/api/v1/users/42/notifications/prices")
    assert await_args.kwargs["json"] == {"drop_warning_threshold": 1.5}
