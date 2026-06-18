"""Доступ к T-Invest: купонный календарь по облигациям из портфелей подписчиков."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from core.clients.t_invest.common_func import to_float
from features.users.repository import BotUserRepository
from t_tech.invest import AsyncClient

from .schemas import CouponPlan

logger = logging.getLogger(__name__)

# Горизонт загрузки плановых купонов вперёд.
HORIZON_DAYS = 60


def _is_ru_isin(isin: str | None) -> bool:
    """Возвращает, относится ли ISIN к периметру НРД (рублёвые ``RU*``)."""
    return bool(isin) and isin.startswith("RU")


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
    plans: list[CouponPlan] = []

    async with AsyncClient(token) as client:
        all_bonds = await client.instruments.bonds()
        bonds_cache = {bond.figi: bond for bond in all_bonds.instruments}

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

                coupons = await client.instruments.get_bond_coupons(
                    figi=figi, from_=now, to=horizon
                )
                plans.extend(
                    CouponPlan(
                        isin=bond.isin,
                        figi=figi,
                        coupon_number=coupon.coupon_number,
                        coupon_date=coupon.coupon_date.date(),
                        amount=(
                            to_float(coupon.pay_one_bond)
                            if coupon.pay_one_bond
                            else None
                        ),
                        bond_name=bond.name,
                        issuer_name=None,
                    )
                    for coupon in coupons.events
                )

    return plans
