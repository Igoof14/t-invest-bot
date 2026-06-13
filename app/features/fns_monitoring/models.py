"""Модели фичи мониторинга блокировок ФНС: подписки и состояние блокировок."""

from datetime import datetime

from core.database import Base
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column


class FnsAlertSettings(Base):
    """Подписка пользователя на уведомления о блокировках счетов ФНС.

    Одна строка на ``telegram_id`` — без разбивки по источникам.
    """

    __tablename__ = "fns_alert_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )

    alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    def __repr__(self) -> str:
        """Представление модели."""
        return (
            f"<FnsAlertSettings(telegram_id={self.telegram_id}, "
            f"enabled={self.alerts_enabled})>"
        )


class FnsBlockingRecord(Base):
    """Решение о приостановлении операций по счетам (состояние дедупа).

    Одна строка на пару (inn, block_uid), где ``block_uid`` = ``"{БИК}:{номер}"``.
    """

    __tablename__ = "fns_blocking_records"
    __table_args__ = (
        UniqueConstraint("inn", "block_uid", name="uq_fns_blocking_records_inn_uid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inn: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    # Стабильный идентификатор решения: f"{bik}:{nomer}".
    block_uid: Mapped[str] = mapped_column(String(64), nullable=False)

    bik: Mapped[str | None] = mapped_column(String(16), nullable=True)
    nomer: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decision_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    date_begin: Mapped[str | None] = mapped_column(String(32), nullable=True)
    kod_osnov: Mapped[str | None] = mapped_column(String(8), nullable=True)
    saldo: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ifns: Mapped[str | None] = mapped_column(String(16), nullable=True)
    entity_name: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Жизненный цикл: "active" — блокировка действует, "resolved" — снята.
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")

    # Момент первого обнаружения блокировки ботом ("когда заблокирован").
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        """Представление модели."""
        return (
            f"<FnsBlockingRecord(inn={self.inn}, block_uid={self.block_uid}, "
            f"status={self.status})>"
        )
