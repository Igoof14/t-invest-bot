"""Доступ к T-Invest: купонный календарь по облигациям из портфелей подписчиков."""

from __future__ import annotations

import logging
from asyncio import sleep
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import TypeVar

from core.clients.t_invest.common_func import to_float
from features.users.repository import BotUserRepository
from grpc import StatusCode
from t_tech.invest import AsyncClient
from t_tech.invest.async_services import AsyncServices
from t_tech.invest.exceptions import AioRequestError, RequestError
from t_tech.invest.schemas import Bond, Coupon

from .schemas import CouponPlan

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Горизонт загрузки плановых купонов вперёд.
HORIZON_DAYS = 60
# TTL кэша каталога облигаций (он одинаков для всех пользователей).
_BONDS_TTL = timedelta(hours=1)
# TTL кэша купонного календаря по бумаге (график стабилен).
_COUPONS_TTL = timedelta(hours=6)
# Широкое окно одной загрузки купонов на бумагу (покрывает скан и синк).
_COUPONS_BACK = timedelta(days=45)
_COUPONS_FWD = timedelta(days=100)
# Сколько раз повторять вызов при RESOURCE_EXHAUSTED.
_RETRY_ATTEMPTS = 4

_bonds_cache: dict[str, Bond] = {}
_bonds_cached_at: datetime | None = None
# figi -> (момент загрузки, события купонов за широкое окно).
_coupons_cache: dict[str, tuple[datetime, list[Coupon]]] = {}


def _is_ru_isin(isin: str | None) -> bool:
    """Возвращает, относится ли ISIN к периметру НРД (рублёвые ``RU*``)."""
    return bool(isin) and isin.startswith("RU")


async def _with_ratelimit_retry(factory: Callable[[], Awaitable[T]]) -> T:
    """Вызывает T-Invest-операцию, переживая ``RESOURCE_EXHAUSTED``.

    При превышении лимита ждёт ``ratelimit_reset`` секунд (из метаданных ответа)
    и повторяет; иначе пробрасывает исключение.
    """
    for attempt in range(_RETRY_ATTEMPTS):
        try:
            return await factory()
        except (AioRequestError, RequestError) as e:
            code = getattr(e, "code", None)
            if code != StatusCode.RESOURCE_EXHAUSTED or attempt == _RETRY_ATTEMPTS - 1:
                raise
            reset = getattr(getattr(e, "metadata", None), "ratelimit_reset", None)
            delay = float(reset) + 0.5 if reset else 2.0 * (attempt + 1)
            logger.warning(
                "T-Invest RESOURCE_EXHAUSTED, повтор через %.1fс (попытка %d)",
                delay,
                attempt + 1,
            )
            await sleep(delay)
    raise RuntimeError("недостижимо")  # для типизации


async def _get_bonds_cache(client: AsyncServices) -> dict[str, Bond]:
    """Возвращает кэш ``{figi: Bond}`` каталога облигаций (с TTL).

    Каталог одинаков для всех пользователей, поэтому кэшируется на уровне модуля —
    это убирает самый тяжёлый повторяемый вызов ``instruments.bonds()``.
    """
    global _bonds_cache, _bonds_cached_at
    now = datetime.now(UTC)
    if _bonds_cache and _bonds_cached_at and now - _bonds_cached_at < _BONDS_TTL:
        return _bonds_cache
    all_bonds = await _with_ratelimit_retry(client.instruments.bonds)
    _bonds_cache = {bond.figi: bond for bond in all_bonds.instruments}
    _bonds_cached_at = now
    return _bonds_cache


async def _get_coupons(client: AsyncServices, figi: str) -> list[Coupon]:
    """Возвращает купонный календарь бумаги за широкое окно (с TTL-кэшем).

    Одна загрузка на бумагу обслуживает и скан (вчера/сегодня), и синк (горизонт),
    резко снижая число вызовов ``get_bond_coupons`` (и риск ``RESOURCE_EXHAUSTED``).
    """
    now = datetime.now(UTC)
    cached = _coupons_cache.get(figi)
    if cached and now - cached[0] < _COUPONS_TTL:
        return cached[1]
    response = await _with_ratelimit_retry(
        lambda: client.instruments.get_bond_coupons(
            figi=figi, from_=now - _COUPONS_BACK, to=now + _COUPONS_FWD
        )
    )
    events = list(response.events)
    _coupons_cache[figi] = (now, events)
    return events


async def collect_coupon_plans(
    telegram_id: int,
    horizon_days: int = HORIZON_DAYS,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[CouponPlan]:
    """Собирает плановые купоны по облигациям портфеля пользователя.

    Берёт токен пользователя, обходит счета и для каждой уникальной облигации
    (с рублёвым ISIN) запрашивает купонный календарь T-Invest за период.

    Args:
        telegram_id: Telegram ID пользователя.
        horizon_days: Горизонт вперёд (если ``date_from``/``date_to`` не заданы).
        date_from: Начало периода купонов (по умолчанию — сейчас).
        date_to: Конец периода купонов (по умолчанию — ``date_from`` + горизонт).

    Returns:
        Список плановых купонов; пустой, если токена нет или облигаций нет.

    """
    token = await BotUserRepository.get_token_by_telegram_id(telegram_id=telegram_id)
    if not token:
        return []

    now = date_from or datetime.now(UTC)
    horizon = date_to or (now + timedelta(days=horizon_days))
    from_date, to_date = now.date(), horizon.date()
    plans: list[CouponPlan] = []

    async with AsyncClient(token) as client:
        bonds_cache = await _get_bonds_cache(client)

        accounts = await client.users.get_accounts()
        seen_figi: set[str] = set()

        for account in accounts.accounts:
            portfolio = await client.operations.get_portfolio(account_id=account.id)
            for position in portfolio.positions:
                if position.instrument_type != "bond":
                    continue
                figi = position.figi
                if figi in seen_figi:
                    continue
                seen_figi.add(figi)

                bond = bonds_cache.get(figi)
                if bond is None or not _is_ru_isin(bond.isin):
                    continue

                for coupon in await _get_coupons(client, figi):
                    coupon_date = coupon.coupon_date.date()
                    if not (from_date <= coupon_date <= to_date):
                        continue
                    plans.append(
                        CouponPlan(
                            isin=bond.isin,
                            figi=figi,
                            coupon_number=coupon.coupon_number,
                            coupon_date=coupon_date,
                            amount=(
                                to_float(coupon.pay_one_bond)
                                if coupon.pay_one_bond
                                else None
                            ),
                            bond_name=bond.name,
                            issuer_name=None,
                        )
                    )

    return plans
