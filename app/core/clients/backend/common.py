"""Общие модели и разбор ответов бэкенда.

Числа бэкенд отдаёт строками (это Decimal), даты — в формате ISO.
"""

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass
class PositionAccount:
    """Позиция по облигации на конкретном счёте."""

    broker: str
    account_id: str
    account_name: str
    quantity: float


def to_float(value: Any) -> float | None:
    """Число из строки-Decimal или ``None``."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_date(value: Any) -> date | None:
    """Дата из ISO-строки или ``None``."""
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def parse_accounts(raw: Any) -> list[PositionAccount]:
    """Разбирает список счетов из ответа бэкенда."""
    return [
        PositionAccount(
            broker=acc.get("broker", ""),
            account_id=acc.get("account_id", ""),
            account_name=acc.get("account_name") or acc.get("account_id", ""),
            quantity=to_float(acc.get("quantity")) or 0.0,
        )
        for acc in raw or []
    ]


def moex_link(secid: str) -> str:
    """Ссылка на страницу выпуска на MOEX."""
    return f"https://www.moex.com/ru/issue.aspx?code={secid}"
