"""Модели фичи мониторинга купонов: подписки и трекинг ожидаемых купонов."""

from datetime import date, datetime, time

from core.database import Base
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column


class NsdCouponAlertSettings(Base):
    """Подписка пользователя на уведомления о невыплаченных купонах.

    Одна строка на ``telegram_id``.
    """

    __tablename__ = "nsd_coupon_alert_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)

    alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    # Время ежедневного отчёта по МСК; ``None`` — отчёт выключен.
    report_time: Mapped[time | None] = mapped_column(Time, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    def __repr__(self) -> str:
        """Представление модели."""
        return (
            f"<NsdCouponAlertSettings(telegram_id={self.telegram_id}, "
            f"enabled={self.alerts_enabled})>"
        )


class NsdCouponTracking(Base):
    """Ожидаемый купон по облигации из портфеля подписчика (состояние проверки).

    Одна строка на пару (isin, coupon_number). Жизненный цикл ``status``:
    ``pending`` — ждём подтверждения выплаты; ``paid`` — НРД опубликовал выплату;
    ``alerted`` — плановая дата прошла без публикации, пользователи уведомлены.
    """

    __tablename__ = "nsd_coupon_tracking"
    __table_args__ = (
        UniqueConstraint("isin", "coupon_number", name="uq_nsd_coupon_tracking_isin_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    isin: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    figi: Mapped[str | None] = mapped_column(String(32), nullable=True)
    coupon_number: Mapped[int] = mapped_column(Integer, nullable=False)
    coupon_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    bond_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    issuer_name: Mapped[str | None] = mapped_column(String(512), nullable=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    # Идентификатор публикации НРД, подтвердившей выплату (если найдена).
    nsd_news_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    alerted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        """Представление модели."""
        return (
            f"<NsdCouponTracking(isin={self.isin}, "
            f"coupon_number={self.coupon_number}, status={self.status})>"
        )
