"""Тесты сервиса-оркестратора уведомлений об офертах."""

from __future__ import annotations

from datetime import date, datetime, time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from apscheduler.triggers.date import DateTrigger
from features.offer_warning import service
from features.offer_warning.service import MSK_TZ, OfferAlertService

_TODAY = date(2026, 6, 1)


def _settings(**overrides: object) -> SimpleNamespace:
    """Создаёт объект настроек с дефолтами для тестов."""
    data: dict[str, object] = {
        "first_alert": 14,
        "second_alert": 5,
        "notification_time": time(10, 0),
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _patch_moex(monkeypatch: pytest.MonkeyPatch, offers_by_isin: dict) -> None:
    """Подменяет MoexClient на мок-контекст-менеджер с заданными офертами."""
    client = MagicMock()
    client.get_many_next_bond_offers = AsyncMock(return_value=offers_by_isin)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(service, "MoexClient", MagicMock(return_value=cm))


# --- _get_matching_offers ---------------------------------------------------


async def test_matching_offers_empty_when_no_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        service.OfferSettingsRepository, "get", AsyncMock(return_value=None)
    )
    result = await OfferAlertService._get_matching_offers(1, _TODAY)
    assert result == []


async def test_matching_offers_empty_when_no_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        service.OfferSettingsRepository, "get", AsyncMock(return_value=_settings())
    )
    monkeypatch.setattr(
        service.BotUserRepository,
        "get_token_by_telegram_id",
        AsyncMock(return_value=""),
    )
    result = await OfferAlertService._get_matching_offers(1, _TODAY)
    assert result == []


async def test_matching_offers_empty_when_no_isins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        service.OfferSettingsRepository, "get", AsyncMock(return_value=_settings())
    )
    monkeypatch.setattr(
        service.BotUserRepository,
        "get_token_by_telegram_id",
        AsyncMock(return_value="token"),
    )
    monkeypatch.setattr(
        service, "get_portfolio_bond_isins", AsyncMock(return_value=[])
    )
    result = await OfferAlertService._get_matching_offers(1, _TODAY)
    assert result == []


async def test_matching_offers_filters_by_thresholds(
    monkeypatch: pytest.MonkeyPatch, offer_factory
) -> None:
    monkeypatch.setattr(
        service.OfferSettingsRepository, "get", AsyncMock(return_value=_settings())
    )
    monkeypatch.setattr(
        service.BotUserRepository,
        "get_token_by_telegram_id",
        AsyncMock(return_value="token"),
    )
    monkeypatch.setattr(
        service, "get_portfolio_bond_isins", AsyncMock(return_value=["A", "B", "C"])
    )
    in_first = offer_factory(secid="A", offerdate=date(2026, 6, 15))  # +14
    in_second = offer_factory(secid="B", offerdate=date(2026, 6, 6))  # +5
    not_matched = offer_factory(secid="C", offerdate=date(2026, 6, 11))  # +10
    _patch_moex(
        monkeypatch,
        {"A": in_first, "B": in_second, "C": not_matched, "D": None},
    )

    result = await OfferAlertService._get_matching_offers(1, _TODAY)
    assert {o.secid for o in result} == {"A", "B"}


# --- schedule_daily_jobs -----------------------------------------------------


@pytest.fixture
def _freeze_now(monkeypatch: pytest.MonkeyPatch) -> None:
    """Фиксирует now() сервиса на 08:00 МСК 2026-06-01, combine — реальный."""

    class _FixedDateTime:
        @classmethod
        def now(cls, tz=None) -> datetime:  # noqa: ANN001
            return datetime(2026, 6, 1, 8, 0, tzinfo=tz or MSK_TZ)

        @classmethod
        def combine(cls, *args, **kwargs) -> datetime:  # noqa: ANN002, ANN003
            return datetime.combine(*args, **kwargs)

    monkeypatch.setattr(service, "datetime", _FixedDateTime)


def _scheduler(existing_job: object | None = None) -> MagicMock:
    sched = MagicMock()
    sched.get_job = MagicMock(return_value=existing_job)
    sched.add_job = MagicMock()
    return sched


async def test_schedule_no_users_does_nothing(
    monkeypatch: pytest.MonkeyPatch, _freeze_now: None
) -> None:
    monkeypatch.setattr(
        service.OfferSettingsRepository,
        "list_users_with_alerts_enabled",
        AsyncMock(return_value=[]),
    )
    sched = _scheduler()
    await OfferAlertService.schedule_daily_jobs(MagicMock(), sched)
    sched.add_job.assert_not_called()


async def test_schedule_skips_when_settings_none(
    monkeypatch: pytest.MonkeyPatch, _freeze_now: None, offer_factory
) -> None:
    monkeypatch.setattr(
        service.OfferSettingsRepository,
        "list_users_with_alerts_enabled",
        AsyncMock(return_value=[1]),
    )
    monkeypatch.setattr(
        OfferAlertService,
        "_get_matching_offers",
        AsyncMock(return_value=[offer_factory()]),
    )
    monkeypatch.setattr(
        service.OfferSettingsRepository, "get", AsyncMock(return_value=None)
    )
    sched = _scheduler()
    await OfferAlertService.schedule_daily_jobs(MagicMock(), sched)
    sched.add_job.assert_not_called()


async def test_schedule_skips_when_time_passed(
    monkeypatch: pytest.MonkeyPatch, _freeze_now: None, offer_factory
) -> None:
    monkeypatch.setattr(
        service.OfferSettingsRepository,
        "list_users_with_alerts_enabled",
        AsyncMock(return_value=[1]),
    )
    monkeypatch.setattr(
        OfferAlertService,
        "_get_matching_offers",
        AsyncMock(return_value=[offer_factory()]),
    )
    monkeypatch.setattr(
        service.OfferSettingsRepository,
        "get",
        AsyncMock(return_value=_settings(notification_time=time(7, 0))),
    )
    sched = _scheduler()
    await OfferAlertService.schedule_daily_jobs(MagicMock(), sched)
    sched.add_job.assert_not_called()


async def test_schedule_skips_when_job_exists(
    monkeypatch: pytest.MonkeyPatch, _freeze_now: None, offer_factory
) -> None:
    monkeypatch.setattr(
        service.OfferSettingsRepository,
        "list_users_with_alerts_enabled",
        AsyncMock(return_value=[1]),
    )
    monkeypatch.setattr(
        OfferAlertService,
        "_get_matching_offers",
        AsyncMock(return_value=[offer_factory()]),
    )
    monkeypatch.setattr(
        service.OfferSettingsRepository, "get", AsyncMock(return_value=_settings())
    )
    sched = _scheduler(existing_job=object())
    await OfferAlertService.schedule_daily_jobs(MagicMock(), sched)
    sched.add_job.assert_not_called()


async def test_schedule_adds_job_on_happy_path(
    monkeypatch: pytest.MonkeyPatch, _freeze_now: None, offer_factory
) -> None:
    monkeypatch.setattr(
        service.OfferSettingsRepository,
        "list_users_with_alerts_enabled",
        AsyncMock(return_value=[42]),
    )
    monkeypatch.setattr(
        OfferAlertService,
        "_get_matching_offers",
        AsyncMock(return_value=[offer_factory()]),
    )
    monkeypatch.setattr(
        service.OfferSettingsRepository, "get", AsyncMock(return_value=_settings())
    )
    sched = _scheduler()
    await OfferAlertService.schedule_daily_jobs(MagicMock(), sched)

    sched.add_job.assert_called_once()
    _, kwargs = sched.add_job.call_args
    assert kwargs["id"] == f"offer_alert_42_{_TODAY}"
    assert isinstance(sched.add_job.call_args.args[1], DateTrigger)


# --- send_notifications ------------------------------------------------------


async def test_send_notifications_delegates_to_notifier(
    monkeypatch: pytest.MonkeyPatch, offer_factory
) -> None:
    notifier = MagicMock()
    notifier.send = AsyncMock()
    monkeypatch.setattr(
        service, "OfferAlertNotifier", MagicMock(return_value=notifier)
    )
    offers = [offer_factory()]
    bot = MagicMock()

    await OfferAlertService.send_notifications(bot=bot, telegram_id=7, offers=offers)

    notifier.send.assert_awaited_once_with(7, offers)
