"""Клиент бэкенда: аналитика денежного потока по облигациям пользователя.

Метрики намеренно остаются списком, а не набором полей: их состав задаёт бэкенд
(`app/analytics/metrics.py` там), и новая строка отчёта не должна требовать правок
ни здесь, ни во фронтенде. Поэтому клиент разбирает *форму* ответа — периоды,
серии, колонки, — но ничего не знает про купоны и налоги.
"""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

from .common import to_date, to_float
from .http import request

logger = logging.getLogger(__name__)

# Гранулярности, которые понимает бэкенд. Всё остальное — мусор в query, и
# отчёт открывается с месяцами, а не падает.
GRANULARITIES = ("day", "week", "month")
DEFAULT_GRANULARITY = "month"

# Столько бумаг показывает таблица, если мини-апп не попросил иначе.
DEFAULT_BONDS_LIMIT = 20
_MIN_LIMIT = 1
_MAX_LIMIT = 50


@dataclass
class Period:
    """Одна колонка сводной таблицы."""

    key: str
    label: str
    start: date | None
    end: date | None


@dataclass
class MetricSeries:
    """Одна строка сводной таблицы: метрика по всем периодам и её итог.

    `values` позиционно соответствует `periods` — та же длина, тот же порядок.
    """

    key: str
    label: str
    sign: str | None
    values: list[float]
    total: float


@dataclass
class Cashflow:
    """Сводная таблица: периоды-колонки и метрики-строки."""

    granularity: str
    date_from: date | None
    date_to: date | None
    periods: list[Period]
    metrics: list[MetricSeries]


@dataclass
class MetricColumn:
    """Одна колонка таблицы по бумагам."""

    key: str
    label: str
    sign: str | None


@dataclass
class BondRow:
    """Одна бумага: значения метрик за диапазон, ключ — `MetricColumn.key`."""

    isin: str
    ticker: str | None
    name: str | None
    events: int
    values: dict[str, float]


@dataclass
class BondBreakdown:
    """Разрез метрик по бумагам, по убыванию чистого потока."""

    date_from: date | None
    date_to: date | None
    columns: list[MetricColumn]
    items: list[BondRow]


def _amount(value: Any) -> float:
    return to_float(value) or 0.0


def _period(raw: dict[str, Any]) -> Period:
    return Period(
        key=raw.get("key", ""),
        label=raw.get("label", ""),
        start=to_date(raw.get("start")),
        end=to_date(raw.get("end")),
    )


def _series(raw: dict[str, Any]) -> MetricSeries:
    return MetricSeries(
        key=raw.get("key", ""),
        label=raw.get("label", ""),
        sign=raw.get("sign"),
        values=[_amount(value) for value in raw.get("values") or []],
        total=_amount(raw.get("total")),
    )


def _column(raw: dict[str, Any]) -> MetricColumn:
    return MetricColumn(key=raw.get("key", ""), label=raw.get("label", ""), sign=raw.get("sign"))


def _bond_row(raw: dict[str, Any]) -> BondRow:
    values = raw.get("values") or {}
    return BondRow(
        isin=raw.get("isin", ""),
        ticker=raw.get("ticker"),
        name=raw.get("name"),
        events=raw.get("events") or 0,
        values={key: _amount(value) for key, value in values.items()},
    )


def _range_params(date_from: date | None, date_to: date | None) -> dict[str, str]:
    """Границы диапазона в query. Пропущенный край бэкенд заполняет сам."""
    params: dict[str, str] = {}
    if date_from is not None:
        params["date_from"] = date_from.isoformat()
    if date_to is not None:
        params["date_to"] = date_to.isoformat()
    return params


async def get_cashflow(
    telegram_id: int,
    granularity: str = DEFAULT_GRANULARITY,
    date_from: date | None = None,
    date_to: date | None = None,
) -> Cashflow:
    """Денежный поток пользователя по периодам.

    Args:
        telegram_id: Telegram ID пользователя.
        granularity: `day`, `week` или `month`.
        date_from: Начало диапазона; без него — первая операция пользователя.
        date_to: Конец диапазона; без него — сегодня.

    Returns:
        Отчёт; у пользователя без операций — пустые `periods` и `metrics`.

    Raises:
        BackendError: Ошибка конфигурации, авторизации или запроса.
        UserNotFound: Бэкенд не знает такого пользователя.

    """
    if granularity not in GRANULARITIES:
        granularity = DEFAULT_GRANULARITY
    payload = await request(
        "GET",
        f"/api/v1/users/{telegram_id}/analytics/cashflow",
        params={"granularity": granularity, **_range_params(date_from, date_to)},
    )
    return Cashflow(
        granularity=payload.get("granularity") or granularity,
        date_from=to_date(payload.get("date_from")),
        date_to=to_date(payload.get("date_to")),
        periods=[_period(item) for item in payload.get("periods") or []],
        metrics=[_series(item) for item in payload.get("metrics") or []],
    )


async def get_bond_breakdown(
    telegram_id: int,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = DEFAULT_BONDS_LIMIT,
) -> BondBreakdown:
    """Те же метрики в разрезе бумаг, по убыванию чистого потока.

    Args:
        telegram_id: Telegram ID пользователя.
        date_from: Начало диапазона; без него — первая операция пользователя.
        date_to: Конец диапазона; без него — сегодня.
        limit: Сколько бумаг вернуть (1..50).

    Returns:
        Таблица; у пользователя без операций — пустые `columns` и `items`.

    Raises:
        BackendError: Ошибка конфигурации, авторизации или запроса.
        UserNotFound: Бэкенд не знает такого пользователя.

    """
    payload = await request(
        "GET",
        f"/api/v1/users/{telegram_id}/analytics/bonds",
        params={
            "limit": max(_MIN_LIMIT, min(limit, _MAX_LIMIT)),
            **_range_params(date_from, date_to),
        },
    )
    return BondBreakdown(
        date_from=to_date(payload.get("date_from")),
        date_to=to_date(payload.get("date_to")),
        columns=[_column(item) for item in payload.get("columns") or []],
        items=[_bond_row(item) for item in payload.get("items") or []],
    )
