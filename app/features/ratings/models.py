"""Модель пользовательских настроек уведомлений о рейтингах."""

from datetime import datetime

from core.database import Base
from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column


class RatingAlertSettings(Base):
    """Подписка пользователя на уведомления конкретного агентства.

    Одна строка на пару (telegram_id, agency) — добавление нового агентства не
    требует миграции схемы.
    """

    __tablename__ = "rating_alert_settings"
    __table_args__ = (
        UniqueConstraint("telegram_id", "agency", name="uq_rating_alert_settings_user_agency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    # Значение RatingAgency (например, "nra").
    agency: Mapped[str] = mapped_column(String(16), nullable=False)

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
            f"<RatingAlertSettings(telegram_id={self.telegram_id}, "
            f"agency={self.agency}, enabled={self.alerts_enabled})>"
        )
