"""Доменные модели блокировок счетов ФНС."""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel


class BlockingOrder(BaseModel):
    """Одно решение о приостановлении операций по счетам (строка ответа ФНС)."""

    inn: str
    block_uid: str

    entity_name: str | None = None
    bik: str | None = None
    nomer: str | None = None
    decision_date: str | None = None
    date_begin: str | None = None
    kod_osnov: str | None = None
    saldo: str | None = None
    ifns: str | None = None


@dataclass
class ResolvedBlock:
    """Новые блокировки эмитента, привязанные к его облигациям из реестра."""

    inn: str
    entity_name: str | None
    new_orders: list[BlockingOrder]
    identifiers: set[str] = field(default_factory=set)
    name_by_id: dict[str, str] = field(default_factory=dict)


@dataclass
class UserBlockAlert:
    """Новые блокировки эмитента, затрагивающие портфель конкретного пользователя."""

    inn: str
    entity_name: str | None
    orders: list[BlockingOrder]
    matched_bond_names: list[str]


@dataclass
class UserScanReport:
    """Результат разовой проверки эмитентов пользователя по запросу."""

    checked: int = 0
    blocked: list[UserBlockAlert] = field(default_factory=list)
    no_token: bool = False
    no_bonds: bool = False


def _clean(value: object) -> str | None:
    """Приводит значение поля ФНС к очищенной строке или ``None``."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_rows(inn: str, result: dict) -> list[BlockingOrder]:
    """Преобразует строки ответа ФНС в список решений о блокировке.

    Args:
        inn: ИНН организации (запрошенный).
        result: JSON-ответ сервиса ФНС (``rows`` — список решений).

    Returns:
        Список ``BlockingOrder`` (пустой, если блокировок нет).

    """
    orders: list[BlockingOrder] = []
    for row in result.get("rows", []):
        bik = _clean(row.get("BIK"))
        nomer = _clean(row.get("NOMER"))
        block_uid = f"{bik or '-'}:{nomer or '-'}"
        orders.append(
            BlockingOrder(
                inn=inn,
                block_uid=block_uid,
                entity_name=_clean(row.get("NAIM")),
                bik=bik,
                nomer=nomer,
                decision_date=_clean(row.get("DATA")),
                date_begin=_clean(row.get("DATABEGIN")),
                kod_osnov=_clean(row.get("KODOSNOV")),
                saldo=_clean(row.get("SALDOENS")),
                ifns=_clean(row.get("IFNS")),
            )
        )
    return orders
