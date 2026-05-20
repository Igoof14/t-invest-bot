from datetime import date, datetime
from typing import Optional

from models.base import Base
from sqlalchemy import BigInteger, Date, DateTime, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column


class BondOffer(Base):
    """Модель данных с информацией о ближайшей офрете по облигации."""

    __tablename__ = "imoex_bond_offers"

    isin: Mapped[str] = mapped_column(String(12), primary_key=True)
    offer_date: Mapped[date] = mapped_column(Date, primary_key=True)
    offer_date_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    offer_date_end: Mapped[date | None] = mapped_column(Date, nullable=True)

    offer_type: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    secid: Mapped[str] = mapped_column(String(12), nullable=False)
    primary_boardid: Mapped[str | None] = mapped_column(String(10))

    face_value: Mapped[Numeric | None] = mapped_column(Numeric(18, 2))
    face_unit: Mapped[str | None] = mapped_column(String(10))
    issue_value: Mapped[int | None] = mapped_column(BigInteger)
    price: Mapped[Numeric | None] = mapped_column(Numeric(10, 4))
    value: Mapped[String | None] = mapped_column(Numeric(18, 2))
    agent: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )
