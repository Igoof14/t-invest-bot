"""Клиент бэкенда: купонные выплаты по облигациям пользователя за дату.

В отличие от оферт и погашений ресурс не листается по «ближайшим N»: он
отвечает на вопрос «что платят в этот день», поэтому вместо ``limit`` у него
``date``, и общий ``fetch_user_items`` здесь не подходит.
"""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

from .common import PositionAccount, moex_link, parse_accounts, to_date, to_float
from .http import request

logger = logging.getLogger(__name__)


@dataclass
class DisclosureInfo:
    """Что эмитент раскрыл про эту выплату."""

    total_payment_amount: float | None
    payment_per_security_value: float | None
    event_url: str | None


@dataclass
class NsdInfo:
    """Дошли ли деньги до НДЦ.

    Бэкенд источник ещё не подключил и отдаёт значения по умолчанию, поэтому
    ``is_paid=False`` без ``url`` означает «не знаем», а не «не заплатили» —
    отличить эти два случая может только фронтенд, и только по наличию ссылки.
    """

    is_paid: bool
    url: str | None


@dataclass
class CouponItem:
    """Купон, выплачиваемый в запрошенную дату, и статус его раскрытия."""

    secid: str
    isin: str
    shortname: str
    name: str
    facevalue: float | None
    faceunit: str
    maturity_date: date | None
    coupon_date: date | None
    coupon_start_date: date | None
    coupon_value: float | None
    total_value: float | None
    is_disclosure: bool
    disclosure: DisclosureInfo | None
    nsd: NsdInfo
    quantity: float
    accounts: list[PositionAccount]

    @property
    def moex_link(self) -> str:
        """Ссылка на страницу выпуска на MOEX."""
        return moex_link(self.secid)


@dataclass
class CouponPayments:
    """Ответ ресурса целиком: за какую дату он собран и что в ней платят."""

    date: date | None
    items: list[CouponItem]


def _parse_disclosure(raw: Any) -> DisclosureInfo | None:
    if not raw:
        return None
    return DisclosureInfo(
        total_payment_amount=to_float(raw.get("total_payment_amount")),
        payment_per_security_value=to_float(raw.get("payment_per_security_value")),
        event_url=raw.get("event_url") or None,
    )


def _parse_nsd(raw: Any) -> NsdInfo:
    raw = raw or {}
    return NsdInfo(is_paid=bool(raw.get("is_paid")), url=raw.get("url") or None)


def _parse_item(raw: dict[str, Any]) -> CouponItem:
    bond = raw.get("bond") or {}
    coupon = raw.get("coupon") or {}
    return CouponItem(
        secid=bond.get("secid", ""),
        isin=bond.get("isin", ""),
        shortname=bond.get("shortname") or bond.get("secid", ""),
        name=bond.get("name", ""),
        facevalue=to_float(bond.get("facevalue")),
        faceunit=bond.get("faceunit") or "",
        maturity_date=to_date(bond.get("matdate")),
        coupon_date=to_date(coupon.get("date")),
        coupon_start_date=to_date(coupon.get("start_date")),
        coupon_value=to_float(coupon.get("value_rub")),
        total_value=to_float(raw.get("total_value_rub")),
        is_disclosure=bool(raw.get("is_disclosure")),
        disclosure=_parse_disclosure(raw.get("disclosure")),
        nsd=_parse_nsd(raw.get("nsd")),
        quantity=to_float(raw.get("quantity")) or 0.0,
        accounts=parse_accounts(raw.get("accounts")),
    )


async def get_coupons(telegram_id: int, on_date: date | None = None) -> CouponPayments:
    """Получает купоны пользователя, выплачиваемые в указанную дату.

    Args:
        telegram_id: Telegram ID пользователя.
        on_date: Дата выплаты; ``None`` — «сегодня» по часам бэкенда.

    Returns:
        Дата, за которую собран ответ, и список купонов — пустой, если выплат
        в этот день нет.

    Raises:
        BackendError: Ошибка конфигурации, авторизации или запроса.
        UserNotFound: Бэкенд не знает такого пользователя.

    """
    payload = await request(
        "GET",
        f"/api/v1/users/{telegram_id}/coupons",
        params={"date": on_date.isoformat()} if on_date else None,
    )
    # Дату берём из ответа, а не из аргумента: «сегодня» определяет бэкенд, и
    # у него оно может не совпасть с датой на машине бота.
    return CouponPayments(
        date=to_date(payload.get("date")) or on_date,
        items=[_parse_item(item) for item in payload.get("items") or []],
    )
