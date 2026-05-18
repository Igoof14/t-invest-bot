"""Модели для системы уведомлений о приблежении оферты по облигации."""

from datetime import datetime, time

from models.base import Base
from sqlalchemy import BigInteger, Boolean, DateTime, Integer, Time, func
from sqlalchemy.orm import Mapped, mapped_column


class OfferAlertSettings(Base):
    """Настройки Put-опцион уведомлений пользователя."""

    __tablename__ = "offer_alert_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)

    # Включены ли уведомления
    alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    # За сколько дней отправлять первое и второе уведомления
    first_alert: Mapped[int] = mapped_column(Integer, default=14)
    second_alert: Mapped[int] = mapped_column(Integer, default=5)

    # Время отправки уведомлений по МСК
    notification_time: Mapped[time] = mapped_column(Time, default=time(10, 0), nullable=False)
    # Метаданные
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    def __repr__(self) -> str:
        """Представление модели."""
        return (
            f"<OfferAlertSettings(telegram_id={self.telegram_id}, enabled={self.alerts_enabled})>"
        )
