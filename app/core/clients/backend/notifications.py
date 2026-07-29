"""Клиент бэкенда: настройки уведомлений пользователя.

Таблицами `*_alert_settings` владеет бэкенд, у бота своих моделей больше нет.
Датаклассы ниже повторяют поля ответа — экраны и клавиатуры читают их так же, как
раньше читали ORM-объекты.
"""

import logging
from dataclasses import dataclass, field
from datetime import time
from typing import Any

from .http import request

logger = logging.getLogger(__name__)

_DEFAULT_NOTIFICATION_TIME = time(10, 0)


@dataclass
class OfferAlertSettings:
    """Настройки напоминаний об оферте."""

    alerts_enabled: bool = False
    first_alert: int = 14
    second_alert: int = 5
    notification_time: time = _DEFAULT_NOTIFICATION_TIME


@dataclass
class PriceAlertSettings:
    """Пороги уведомлений об изменении цены, в процентах."""

    alerts_enabled: bool = False
    drop_warning_threshold: float = 2.0
    drop_critical_threshold: float = 5.0
    rise_warning_threshold: float = 3.0
    rise_critical_threshold: float = 7.0


@dataclass
class DisclosureAlertSettings:
    """Подписка на раскрытия эмитентов и минимальный уровень риска."""

    alerts_enabled: bool = False
    # "low" — нижняя граница шкалы, то есть «все события».
    min_risk_level: str = "low"


@dataclass
class NotificationSettings:
    """Состояние всех секций хаба уведомлений."""

    offers: OfferAlertSettings = field(default_factory=OfferAlertSettings)
    prices: PriceAlertSettings = field(default_factory=PriceAlertSettings)
    fns_enabled: bool = False
    enabled_agencies: frozenset[str] = frozenset()
    disclosure: DisclosureAlertSettings = field(default_factory=DisclosureAlertSettings)


def _path(telegram_id: int, suffix: str = "") -> str:
    return f"/api/v1/users/{telegram_id}/notifications{suffix}"


def _parse_time(value: Any) -> time:
    """Время из строки ISO; при неразборчивом значении — дефолт бэкенда."""
    try:
        return time.fromisoformat(str(value))
    except (TypeError, ValueError):
        logger.warning(f"Не удалось разобрать время уведомления: {value!r}")
        return _DEFAULT_NOTIFICATION_TIME


def _offers(raw: dict[str, Any]) -> OfferAlertSettings:
    defaults = OfferAlertSettings()
    return OfferAlertSettings(
        alerts_enabled=bool(raw.get("alerts_enabled")),
        first_alert=int(raw.get("first_alert") or defaults.first_alert),
        second_alert=int(raw.get("second_alert") or defaults.second_alert),
        notification_time=_parse_time(raw.get("notification_time")),
    )


def _prices(raw: dict[str, Any]) -> PriceAlertSettings:
    defaults = PriceAlertSettings()
    return PriceAlertSettings(
        alerts_enabled=bool(raw.get("alerts_enabled")),
        drop_warning_threshold=float(
            raw.get("drop_warning_threshold") or defaults.drop_warning_threshold
        ),
        drop_critical_threshold=float(
            raw.get("drop_critical_threshold") or defaults.drop_critical_threshold
        ),
        rise_warning_threshold=float(
            raw.get("rise_warning_threshold") or defaults.rise_warning_threshold
        ),
        rise_critical_threshold=float(
            raw.get("rise_critical_threshold") or defaults.rise_critical_threshold
        ),
    )


def _disclosure(raw: dict[str, Any]) -> DisclosureAlertSettings:
    defaults = DisclosureAlertSettings()
    return DisclosureAlertSettings(
        alerts_enabled=bool(raw.get("alerts_enabled")),
        min_risk_level=str(raw.get("min_risk_level") or defaults.min_risk_level),
    )


async def get_settings(telegram_id: int) -> NotificationSettings:
    """Забирает состояние всех секций одним запросом.

    Raises:
        BackendError: Ошибка конфигурации, авторизации или запроса.

    """
    payload = await request("GET", _path(telegram_id))
    ratings = payload.get("ratings") or {}
    return NotificationSettings(
        offers=_offers(payload.get("offers") or {}),
        prices=_prices(payload.get("prices") or {}),
        fns_enabled=bool((payload.get("fns") or {}).get("alerts_enabled")),
        enabled_agencies=frozenset(ratings.get("enabled_agencies") or ()),
        disclosure=_disclosure(payload.get("disclosure") or {}),
    )


async def toggle(telegram_id: int, section: str) -> bool:
    """Переключает секцию (`offers`, `prices`, `fns`, `disclosure`) и возвращает состояние.

    Raises:
        BackendError: Ошибка конфигурации, авторизации или запроса.

    """
    payload = await request("POST", _path(telegram_id, f"/{section}/toggle"))
    return bool(payload.get("alerts_enabled"))


async def toggle_agency(telegram_id: int, agency: str) -> bool:
    """Переключает подписку на агентство и возвращает новое состояние.

    Raises:
        BackendError: Ошибка конфигурации, авторизации или запроса.

    """
    payload = await request("POST", _path(telegram_id, f"/ratings/{agency}/toggle"))
    return bool(payload.get("alerts_enabled"))


async def update_offers(telegram_id: int, **fields: Any) -> OfferAlertSettings:
    """Меняет переданные поля настроек оферт; остальные остаются как были.

    Raises:
        BackendError: Ошибка конфигурации, авторизации или запроса.

    """
    body = {
        key: value.isoformat() if isinstance(value, time) else value
        for key, value in fields.items()
    }
    return _offers(await request("PATCH", _path(telegram_id, "/offers"), json=body))


async def update_prices(telegram_id: int, **fields: Any) -> PriceAlertSettings:
    """Меняет переданные пороги цен; остальные остаются как были.

    Raises:
        BackendError: Ошибка конфигурации, авторизации или запроса.

    """
    return _prices(await request("PATCH", _path(telegram_id, "/prices"), json=dict(fields)))


async def update_disclosure(telegram_id: int, **fields: Any) -> DisclosureAlertSettings:
    """Меняет переданные поля настроек раскрытий; остальные остаются как были.

    Raises:
        BackendError: Ошибка конфигурации, авторизации или запроса.

    """
    return _disclosure(
        await request("PATCH", _path(telegram_id, "/disclosure"), json=dict(fields))
    )
