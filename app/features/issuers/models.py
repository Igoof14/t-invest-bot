"""Модели реестра эмитентов и их облигаций."""

from datetime import datetime

from core.database import Base
from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column


class Issuer(Base):
    """Эмитент (компания) по данным MOEX ISS."""

    __tablename__ = "issuers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # MOEX EMITTER_ID — стабильный идентификатор эмитента
    emitter_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)

    inn: Mapped[str | None] = mapped_column(String(12), nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    short_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ogrn: Mapped[str | None] = mapped_column(String(15), nullable=True)
    okpo: Mapped[str | None] = mapped_column(String(10), nullable=True)
    legal_address: Mapped[str | None] = mapped_column(String(512), nullable=True)
    url: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    def __repr__(self) -> str:
        """Представление модели."""
        return f"<Issuer(emitter_id={self.emitter_id}, inn={self.inn})>"


class IssuerBond(Base):
    """Облигация и её связь с эмитентом."""

    __tablename__ = "issuer_bonds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    isin: Mapped[str] = mapped_column(String(12), unique=True, nullable=False, index=True)
    figi: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ticker: Mapped[str | None] = mapped_column(String(32), nullable=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    issuer_id: Mapped[int | None] = mapped_column(
        ForeignKey("issuers.id"), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    def __repr__(self) -> str:
        """Представление модели."""
        return f"<IssuerBond(isin={self.isin}, issuer_id={self.issuer_id})>"
