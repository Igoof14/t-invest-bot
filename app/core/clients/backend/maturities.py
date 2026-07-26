"""Клиент бэкенда: ближайшие погашения облигаций пользователя."""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

from .common import PositionAccount, moex_link, parse_accounts, to_date, to_float
from .http import fetch_user_items

logger = logging.getLogger(__name__)


@dataclass
class MaturityItem:
    """Погашение облигации из портфеля пользователя."""

    secid: str
    isin: str
    shortname: str
    name: str
    facevalue: float | None
    faceunit: str
    maturity_date: date | None
    days_left: int | None
    quantity: float
    accounts: list[PositionAccount]

    @property
    def moex_link(self) -> str:
        """Ссылка на страницу выпуска на MOEX."""
        return moex_link(self.secid)


def _parse_item(raw: dict[str, Any]) -> MaturityItem:
    bond = raw.get("bond") or {}
    maturity = raw.get("maturity") or {}
    return MaturityItem(
        secid=bond.get("secid", ""),
        isin=bond.get("isin", ""),
        shortname=bond.get("shortname") or bond.get("secid", ""),
        name=bond.get("name", ""),
        facevalue=to_float(bond.get("facevalue")),
        faceunit=bond.get("faceunit") or "",
        # Дата погашения приходит и в bond.matdate, и в maturity.date — берём
        # блок maturity как основной, bond.matdate как запасной.
        maturity_date=to_date(maturity.get("date")) or to_date(bond.get("matdate")),
        days_left=maturity.get("days_left"),
        quantity=to_float(raw.get("quantity")) or 0.0,
        accounts=parse_accounts(raw.get("accounts")),
    )


async def get_maturities(telegram_id: int, limit: int = 5) -> list[MaturityItem]:
    """Получает ближайшие погашения пользователя из бэкенда.

    Args:
        telegram_id: Telegram ID пользователя.
        limit: Сколько ближайших погашений вернуть (1..50).

    Returns:
        Список погашений; пустой, если пользователь известен, но погашений нет.

    Raises:
        BackendError: Ошибка конфигурации, авторизации или запроса.
        UserNotFound: Бэкенд не знает такого пользователя.

    """
    items = await fetch_user_items("maturities", telegram_id, limit)
    return [_parse_item(item) for item in items]
