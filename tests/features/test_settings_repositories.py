"""Тесты репозиториев настроек уведомлений.

Данные живут в бэкенде, поэтому проверяется то, за что репозитории теперь отвечают:
зовут нужный метод клиента и не дают его ошибке дойти до хендлера. Переключатели —
исключение: соврать пользователю про новое состояние хуже, чем показать ошибку.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from core.clients.backend.errors import BackendError
from core.clients.backend.notifications import (
    NotificationSettings,
    OfferAlertSettings,
    PriceAlertSettings,
)
from features.fns_monitoring.repository import FnsAlertSettingsRepository
from features.offer_warning.repository import OfferSettingsRepository
from features.price_monitoring.repository import AlertSettingsRepository
from features.ratings.enums import RatingAgency
from features.ratings.repository import RatingAlertSettingsRepository

_MODULES = (
    "features.offer_warning.repository",
    "features.price_monitoring.repository",
    "features.ratings.repository",
    "features.fns_monitoring.repository",
)


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Подменяет клиент бэкенда во всех четырёх репозиториях сразу."""
    mock = AsyncMock()
    mock.get_settings.return_value = NotificationSettings()
    for module in _MODULES:
        monkeypatch.setattr(f"{module}.api", mock)
    return mock


async def test_offers_get_returns_settings(api: AsyncMock) -> None:
    api.get_settings.return_value = NotificationSettings(
        offers=OfferAlertSettings(alerts_enabled=True, first_alert=20)
    )

    settings = await OfferSettingsRepository.get(111)

    assert (settings.alerts_enabled, settings.first_alert) == (True, 20)


async def test_offers_get_falls_back_to_defaults_on_error(api: AsyncMock) -> None:
    api.get_settings.side_effect = BackendError("backend down")

    settings = await OfferSettingsRepository.get(111)

    assert settings.alerts_enabled is False
    assert settings.first_alert == 14


async def test_offers_update_passes_fields(api: AsyncMock) -> None:
    assert await OfferSettingsRepository.update(111, first_alert=20) is True
    api.update_offers.assert_awaited_once_with(111, first_alert=20)


async def test_offers_update_returns_false_on_error(api: AsyncMock) -> None:
    api.update_offers.side_effect = BackendError("backend down")

    assert await OfferSettingsRepository.update(111, first_alert=20) is False


async def test_offers_toggle(api: AsyncMock) -> None:
    api.toggle.return_value = True

    assert await OfferSettingsRepository.toggle_alerts(111) is True
    api.toggle.assert_awaited_once_with(111, "offers")


async def test_toggle_propagates_backend_error(api: AsyncMock) -> None:
    api.toggle.side_effect = BackendError("backend down")

    with pytest.raises(BackendError):
        await OfferSettingsRepository.toggle_alerts(111)


async def test_prices_get_returns_thresholds(api: AsyncMock) -> None:
    api.get_settings.return_value = NotificationSettings(
        prices=PriceAlertSettings(drop_critical_threshold=8.5)
    )

    assert (await AlertSettingsRepository.get(111)).drop_critical_threshold == 8.5


async def test_prices_toggle(api: AsyncMock) -> None:
    api.toggle.return_value = False

    assert await AlertSettingsRepository.toggle_alerts(111) is False
    api.toggle.assert_awaited_once_with(111, "prices")


async def test_fns_is_enabled(api: AsyncMock) -> None:
    api.get_settings.return_value = NotificationSettings(fns_enabled=True)

    assert await FnsAlertSettingsRepository.is_enabled(111) is True


async def test_fns_is_enabled_false_on_error(api: AsyncMock) -> None:
    api.get_settings.side_effect = BackendError("backend down")

    assert await FnsAlertSettingsRepository.is_enabled(111) is False


async def test_fns_toggle(api: AsyncMock) -> None:
    api.toggle.return_value = True

    assert await FnsAlertSettingsRepository.toggle(111) is True
    api.toggle.assert_awaited_once_with(111, "fns")


async def test_rating_enabled_agencies(api: AsyncMock) -> None:
    api.get_settings.return_value = NotificationSettings(enabled_agencies=frozenset({"nra"}))

    assert await RatingAlertSettingsRepository.get_enabled_agencies(111) == {RatingAgency.NRA}


async def test_rating_unknown_agency_is_skipped(api: AsyncMock) -> None:
    """Бэкенд хранит любой код агентства — бот игнорирует те, которых не знает."""
    api.get_settings.return_value = NotificationSettings(
        enabled_agencies=frozenset({"nra", "who-is-this"})
    )

    assert await RatingAlertSettingsRepository.get_enabled_agencies(111) == {RatingAgency.NRA}


async def test_rating_agencies_empty_on_error(api: AsyncMock) -> None:
    api.get_settings.side_effect = BackendError("backend down")

    assert await RatingAlertSettingsRepository.get_enabled_agencies(111) == set()


async def test_rating_toggle_sends_agency_code(api: AsyncMock) -> None:
    api.toggle_agency.return_value = True

    assert await RatingAlertSettingsRepository.toggle(111, RatingAgency.NKR) is True
    api.toggle_agency.assert_awaited_once_with(111, "nkr")
