"""Тесты репозитория подписок на уведомления о рейтингах."""

from __future__ import annotations

import pytest
from features.ratings.enums import RatingAgency
from features.ratings.repository import RatingAlertSettingsRepository

pytestmark = pytest.mark.usefixtures("patch_session_scope")


async def test_get_or_create_defaults_disabled() -> None:
    settings = await RatingAlertSettingsRepository.get_or_create(111, RatingAgency.NRA)

    assert settings.telegram_id == 111
    assert settings.agency == "nra"
    assert settings.alerts_enabled is False


async def test_toggle_turns_on_then_off() -> None:
    assert await RatingAlertSettingsRepository.toggle(111, RatingAgency.NRA) is True
    assert await RatingAlertSettingsRepository.toggle(111, RatingAgency.NRA) is False


async def test_get_enabled_agencies_reflects_toggles() -> None:
    await RatingAlertSettingsRepository.toggle(111, RatingAgency.NRA)

    enabled = await RatingAlertSettingsRepository.get_enabled_agencies(111)
    assert enabled == {RatingAgency.NRA}


async def test_get_enabled_agencies_empty_by_default() -> None:
    await RatingAlertSettingsRepository.get_or_create(111, RatingAgency.NRA)

    assert await RatingAlertSettingsRepository.get_enabled_agencies(111) == set()


async def test_list_users_with_alerts_enabled_only_subscribers() -> None:
    await RatingAlertSettingsRepository.toggle(111, RatingAgency.NRA)  # включил
    await RatingAlertSettingsRepository.get_or_create(222, RatingAgency.NRA)  # выкл

    users = await RatingAlertSettingsRepository.list_users_with_alerts_enabled(
        RatingAgency.NRA
    )
    assert users == [111]
