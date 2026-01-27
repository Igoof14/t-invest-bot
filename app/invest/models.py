"""Модели данных для T-Invest API."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class MoneyValue(BaseModel):
    """Денежное значение."""

    units: int = 0
    nano: int = 0

    def to_float(self) -> float:
        """Конвертирует в float."""
        return self.units + self.nano / 1e9


class Quotation(BaseModel):
    """Котировка."""

    units: int = 0
    nano: int = 0

    def to_float(self) -> float:
        """Конвертирует в float."""
        return self.units + self.nano / 1e9


class Account(BaseModel):
    """Счёт пользователя."""

    id: str
    name: str
    type: str | None = None
    status: str | None = None


class GetAccountsResponse(BaseModel):
    """Ответ на запрос списка счетов."""

    accounts: list[Account] = []


class UserInfo(BaseModel):
    """Информация о пользователе."""

    prem_status: bool = Field(default=False, alias="premStatus")
    qual_status: bool = Field(default=False, alias="qualStatus")
    tariff: str = ""


class OperationType(str, Enum):
    """Типы операций."""

    OPERATION_TYPE_UNSPECIFIED = "OPERATION_TYPE_UNSPECIFIED"
    OPERATION_TYPE_INPUT = "OPERATION_TYPE_INPUT"
    OPERATION_TYPE_OUTPUT = "OPERATION_TYPE_OUTPUT"
    OPERATION_TYPE_BUY = "OPERATION_TYPE_BUY"
    OPERATION_TYPE_SELL = "OPERATION_TYPE_SELL"
    OPERATION_TYPE_COUPON = "OPERATION_TYPE_COUPON"
    OPERATION_TYPE_DIVIDEND = "OPERATION_TYPE_DIVIDEND"
    OPERATION_TYPE_TAX = "OPERATION_TYPE_TAX"
    OPERATION_TYPE_BOND_REPAYMENT = "OPERATION_TYPE_BOND_REPAYMENT"


class Operation(BaseModel):
    """Операция."""

    id: str = ""
    operation_type: str = Field(default="", alias="operationType")
    payment: MoneyValue = Field(default_factory=MoneyValue)
    figi: str = ""
    instrument_type: str = Field(default="", alias="instrumentType")
    date: str = ""


class GetOperationsResponse(BaseModel):
    """Ответ на запрос операций."""

    operations: list[Operation] = []


class PortfolioPosition(BaseModel):
    """Позиция в портфеле."""

    figi: str = ""
    instrument_type: str = Field(default="", alias="instrumentType")
    quantity: Quotation = Field(default_factory=Quotation)
    current_price: Quotation = Field(default_factory=Quotation, alias="currentPrice")
    average_position_price: Quotation | None = Field(default=None, alias="averagePositionPrice")


class GetPortfolioResponse(BaseModel):
    """Ответ на запрос портфеля."""

    total_amount_bonds: MoneyValue = Field(default_factory=MoneyValue, alias="totalAmountBonds")
    positions: list[PortfolioPosition] = []


class Bond(BaseModel):
    """Облигация."""

    figi: str = ""
    ticker: str = ""
    name: str = ""
    nominal: MoneyValue = Field(default_factory=MoneyValue)
    currency: str = ""
    maturity_date: datetime | None = Field(default=None, alias="maturityDate")
    coupon_quantity_per_year: int = Field(default=0, alias="couponQuantityPerYear")


class BondsResponse(BaseModel):
    """Ответ на запрос списка облигаций."""

    instruments: list[Bond] = []


class EventType(str, Enum):
    """Типы событий по облигациям."""

    EVENT_TYPE_UNSPECIFIED = "EVENT_TYPE_UNSPECIFIED"
    EVENT_TYPE_CPN = "EVENT_TYPE_CPN"  # Купон
    EVENT_TYPE_CALL = "EVENT_TYPE_CALL"  # Оферта
    EVENT_TYPE_MTY = "EVENT_TYPE_MTY"  # Погашение
    EVENT_TYPE_CONV = "EVENT_TYPE_CONV"  # Конвертация


class BondEvent(BaseModel):
    """Событие по облигации."""

    event_date: datetime = Field(alias="eventDate")
    event_type: str = Field(default="", alias="eventType")
    event_total_vol: MoneyValue = Field(default_factory=MoneyValue, alias="eventTotalVol")


class GetBondEventsResponse(BaseModel):
    """Ответ на запрос событий по облигации."""

    events: list[BondEvent] = []
