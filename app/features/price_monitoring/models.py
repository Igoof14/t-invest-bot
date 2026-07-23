"""Модели для системы уведомлений о ценах облигаций."""

from datetime import datetime

from core.database import Base
from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, func
from sqlalchemy.orm import Mapped, mapped_column


class PriceAlertSettings(Base):
    """Настройки ценовых уведомлений пользователя."""

    __tablename__ = "price_alert_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)

    # Включены ли уведомления
    alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    # Пороги падения (в процентах)
    drop_warning_threshold: Mapped[float] = mapped_column(Float, default=2.0)
    drop_critical_threshold: Mapped[float] = mapped_column(Float, default=5.0)

    # Пороги роста (в процентах)
    rise_warning_threshold: Mapped[float] = mapped_column(Float, default=3.0)
    rise_critical_threshold: Mapped[float] = mapped_column(Float, default=7.0)

    # Метаданные
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    def __repr__(self) -> str:
        """Представление модели."""
        return f"<UserAlertSettings(telegram_id={self.telegram_id}, enabled={self.alerts_enabled})>"
