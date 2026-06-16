"""Доменные модели данных, извлекаемых из ленты НРД."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class NsdNewsItem:
    """Одна новость из списка ленты НРД (строка поиска по ISIN).

    Attributes:
        news_id: Идентификатор новости (`/ru/news/view/<id>`).
        news_type: Код типа корпоративного действия (``INTR``, ``PRED``, ...).
        title: Полный заголовок новости.
        isin: ISIN бумаги из заголовка (или ``None``, если не найден).
        issuer_name: Наименование эмитента из заголовка (или ``None``).
        inn: ИНН эмитента из заголовка (или ``None``).
        published_at: Дата публикации новости (или ``None``).
    """

    news_id: int
    news_type: str
    title: str
    isin: str | None
    issuer_name: str | None
    inn: str | None
    published_at: date | None


@dataclass(frozen=True)
class CouponPlan:
    """Плановый купон из календаря T-Invest для отслеживания.

    Attributes:
        isin: ISIN облигации.
        figi: FIGI облигации (для повторных обращений к T-Invest).
        coupon_number: Порядковый номер купона.
        coupon_date: Плановая дата выплаты купона.
        amount: Размер купона на одну бумагу (или ``None``).
        bond_name: Название облигации (или ``None``).
        issuer_name: Наименование эмитента (или ``None``).
    """

    isin: str
    figi: str | None
    coupon_number: int
    coupon_date: date
    amount: float | None = None
    bond_name: str | None = None
    issuer_name: str | None = None


@dataclass(frozen=True)
class NsdCardDetails:
    """Детали карточки новости НРД о выплате дохода (INTR).

    Attributes:
        news_type: Код типа корпоративного действия из карточки.
        planned_pay_date: Плановая дата выплаты («Дата выплаты плановая»).
        nsd_received_date: Дата поступления денежных средств в НРД (``None``,
            если средства ещё не поступили — выплаты не было).
        amount_per_bond: Размер выплаты на одну ценную бумагу (или ``None``).
    """

    news_type: str | None
    planned_pay_date: date | None
    nsd_received_date: date | None
    amount_per_bond: float | None
