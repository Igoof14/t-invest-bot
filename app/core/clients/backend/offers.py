"""Клиент бэкенда: ближайшие оферты по облигациям пользователя."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

import aiohttp
from core.config import config
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.oauth2.id_token import fetch_id_token

logger = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=30)


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


def _fetch_id_token(audience: str) -> str | None:
    """Запрашивает OIDC id-token у metadata server GCE (блокирующий вызов)."""
    return fetch_id_token(Request(), audience)


async def _auth_headers(base_url: str) -> dict[str, str]:
    """Заголовки авторизации для приватного Cloud Run сервиса.

    Если id-token получить не удалось (например, при локальном запуске вне GCE),
    возвращает пустой словарь — запрос уйдёт без авторизации.
    """
    try:
        token = await asyncio.to_thread(_fetch_id_token, base_url)
    except GoogleAuthError:
        logger.warning(f"Не удалось получить OIDC id-token для {base_url}", exc_info=True)
        return {}
    return {"Authorization": f"Bearer {token}"} if token else {}


def _to_float(value: Any) -> float | None:
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


async def get_offers(telegram_id: int, limit: int = 5) -> list[OfferItem] | None:
    """Получает ближайшие оферты пользователя из бэкенда.

    Args:
        telegram_id: Telegram ID пользователя.
        limit: Максимальное количество оферт.

    Returns:
        Список оферт (возможно пустой) или ``None``, если запрос не удался.

    """
    base_url = config.backend_url
    if not base_url:
        logger.warning("BACKEND_URL не задан — оферты не получены")
        return None

    base_url = base_url.rstrip("/")
    url = f"{base_url}/{telegram_id}/offers"
    headers = await _auth_headers(base_url)

    try:
        async with (
            aiohttp.ClientSession(timeout=_TIMEOUT) as session,
            session.get(url, params={"limit": limit}, headers=headers) as resp,
        ):
            resp.raise_for_status()
            payload = await resp.json()
    except (aiohttp.ClientError, TimeoutError, ValueError):
        logger.error(f"Ошибка получения оферт для пользователя {telegram_id}", exc_info=True)
        return None

    items = payload.get("items") or []
    return [_parse_item(item) for item in items]
