"""Доменные модели данных, извлекаемых из ленты НРД."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from aiogram.filters.callback_data import CallbackData


class NsdCouponAlertCallback(CallbackData, prefix="nsd_coupon"):
    """Callback data для кнопок раздела уведомлений о купонах."""

    action: Literal["toggle", "scan", "set_report_time"]


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
class CouponMissAlert:
    """Уведомление о невыплаченном в срок купоне.

    Attributes:
        isin: ISIN облигации.
        bond_name: Название облигации (или ``None``).
        issuer_name: Наименование эмитента (или ``None``).
        coupon_number: Порядковый номер купона.
        coupon_date: Плановая дата выплаты, которая прошла без публикации НРД.
        amount: Ожидавшийся размер купона на одну бумагу (или ``None``).
    """

    isin: str
    bond_name: str | None
    issuer_name: str | None
    coupon_number: int
    coupon_date: date
    amount: float | None


@dataclass(frozen=True)
class ScannedCoupon:
    """Результат разовой проверки одного купона по ленте НРД.

    Attributes:
        isin: ISIN облигации.
        bond_name: Название облигации (или ``None``).
        coupon_date: Плановая дата выплаты купона.
        paid: Подтверждена ли выплата публикацией НРД.
    """

    isin: str
    bond_name: str | None
    coupon_date: date
    paid: bool


@dataclass
class CouponScanReport:
    """Итог разовой проверки купонов пользователя за вчера и сегодня.

    Attributes:
        no_token: У пользователя не задан токен T-Invest.
        coupons: Проверенные купоны (за вчера и сегодня).
    """

    no_token: bool = False
    coupons: list[ScannedCoupon] = field(default_factory=list)


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
