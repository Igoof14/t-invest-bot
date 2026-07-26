"""Клиент бэкенда: ближайшие оферты по облигациям пользователя."""

import logging
from dataclasses import dataclass
from datetime import date
from http import HTTPStatus
from typing import Any

import aiohttp
from core.config import config

from .auth import auth_headers
from .errors import BackendError, BackendNotConfigured, UserNotFound

logger = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=30)

# Ограничение эндпоинта на количество возвращаемых оферт.
_MIN_LIMIT = 1
_MAX_LIMIT = 50


@dataclass
class OfferAccount:
    """Позиция по облигации на конкретном счёте."""

    broker: str
    account_id: str
    account_name: str
    quantity: float


@dataclass
class OfferItem:
    """Оферта по облигации из портфеля пользователя."""

    secid: str
    isin: str
    shortname: str
    name: str
    facevalue: float | None
    faceunit: str
    maturity_date: date | None
    offer_date: date | None
    offer_type: str
    date_start: date | None
    date_end: date | None
    price: float | None
    value: float | None
    agent: str | None
    days_left: int | None
    quantity: float
    accounts: list[OfferAccount]

    @property
    def moex_link(self) -> str:
        """Ссылка на страницу выпуска на MOEX."""
        return f"https://www.moex.com/ru/issue.aspx?code={self.secid}"


def _to_float(value: Any) -> float | None:
    """Число из строки (на бэкенде это Decimal) или ``None``."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _parse_item(raw: dict[str, Any]) -> OfferItem:
    bond = raw.get("bond") or {}
    offer = raw.get("offer") or {}
    return OfferItem(
        secid=bond.get("secid", ""),
        isin=bond.get("isin", ""),
        shortname=bond.get("shortname") or bond.get("secid", ""),
        name=bond.get("name", ""),
        facevalue=_to_float(bond.get("facevalue")),
        faceunit=bond.get("faceunit") or "",
        maturity_date=_to_date(bond.get("matdate")),
        offer_date=_to_date(offer.get("date")),
        offer_type=offer.get("type") or "Оферта",
        date_start=_to_date(offer.get("date_start")),
        date_end=_to_date(offer.get("date_end")),
        price=_to_float(offer.get("price")),
        value=_to_float(offer.get("value")),
        agent=offer.get("agent"),
        days_left=offer.get("days_left"),
        quantity=_to_float(raw.get("quantity")) or 0.0,
        accounts=[
            OfferAccount(
                broker=acc.get("broker", ""),
                account_id=acc.get("account_id", ""),
                account_name=acc.get("account_name") or acc.get("account_id", ""),
                quantity=_to_float(acc.get("quantity")) or 0.0,
            )
            for acc in raw.get("accounts") or []
        ],
    )


async def get_offers(telegram_id: int, limit: int = 5) -> list[OfferItem]:
    """Получает ближайшие оферты пользователя из бэкенда.

    Args:
        telegram_id: Telegram ID пользователя.
        limit: Сколько ближайших оферт вернуть (1..50).

    Returns:
        Список оферт; пустой, если пользователь известен, но оферт нет.

    Raises:
        BackendNotConfigured: Не задан `BACKEND_URL`.
        BackendAuthError: Не удалось получить OIDC id-token.
        UserNotFound: Бэкенд не знает такого пользователя.
        BackendError: Прочие ошибки запроса или разбора ответа.

    """
    base_url = config.backend_url
    if not base_url:
        raise BackendNotConfigured("BACKEND_URL не задан")

    base_url = base_url.rstrip("/")
    url = f"{base_url}/api/v1/users/{telegram_id}/offers"
    params = {"limit": max(_MIN_LIMIT, min(limit, _MAX_LIMIT))}
    headers = await auth_headers(base_url)

    try:
        async with (
            aiohttp.ClientSession(timeout=_TIMEOUT) as session,
            session.get(url, params=params, headers=headers) as resp,
        ):
            if resp.status == HTTPStatus.NOT_FOUND:
                raise UserNotFound(f"Пользователь {telegram_id} неизвестен бэкенду")
            resp.raise_for_status()
            payload = await resp.json()
    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
        raise BackendError(f"Ошибка запроса оферт для пользователя {telegram_id}: {exc}") from exc

    return [_parse_item(item) for item in payload.get("items") or []]
