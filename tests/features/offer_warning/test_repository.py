"""Тесты репозитория настроек уведомлений об офертах."""

from __future__ import annotations

from datetime import time

import pytest
from features.offer_warning.repository import OfferSettingsRepository

pytestmark = pytest.mark.usefixtures("patch_session_scope")


async def test_get_returns_none_when_absent() -> None:
    assert await OfferSettingsRepository.get(111) is None


async def test_get_or_create_creates_with_defaults() -> None:
    settings = await OfferSettingsRepository.get_or_create(111)
    assert settings.telegram_id == 111
    assert settings.first_alert == 14
    assert settings.second_alert == 5
    assert settings.notification_time == time(10, 0)
    assert settings.alerts_enabled is False


async def test_get_or_create_returns_existing_without_duplicate() -> None:
    first = await OfferSettingsRepository.get_or_create(111)
    first.first_alert = 99  # локальное изменение не должно влиять
    second = await OfferSettingsRepository.get_or_create(111)
    assert second.id == first.id
    assert second.first_alert == 14
    users = await OfferSettingsRepository.list_users_with_alerts_enabled()
    assert users == []  # запись создана, но алерты выключены


async def test_update_changes_fields() -> None:
    await OfferSettingsRepository.get_or_create(111)
    updated = await OfferSettingsRepository.update(111, first_alert=20)
    assert updated is True
    settings = await OfferSettingsRepository.get(111)
    assert settings is not None
    assert settings.first_alert == 20


async def test_update_autocreates_when_missing() -> None:
    result = await OfferSettingsRepository.update(222, second_alert=3)
    assert result is True
    settings = await OfferSettingsRepository.get(222)
    assert settings is not None
    assert settings.second_alert == 3


async def test_toggle_alerts_flips_value() -> None:
    assert await OfferSettingsRepository.toggle_alerts(111) is True
    assert await OfferSettingsRepository.toggle_alerts(111) is False


async def test_list_users_returns_only_enabled() -> None:
    await OfferSettingsRepository.get_or_create(111)
    await OfferSettingsRepository.toggle_alerts(222)  # включает алерты для 222
    await OfferSettingsRepository.get_or_create(333)

    users = await OfferSettingsRepository.list_users_with_alerts_enabled()
    assert users == [222]
