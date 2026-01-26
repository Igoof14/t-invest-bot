"""Модели для системы уведомлений о ценах облигаций."""

from datetime import datetime

from models.base import Base
from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column


class UserAlertSettings(Base):
    """Настройки уведомлений пользователя."""

    __tablename__ = "user_alert_settings"

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


class BondPriceHistory(Base):
    """История цен облигаций для сравнения."""

    __tablename__ = "bond_price_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    # Идентификаторы облигации
    figi: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Цена в процентах от номинала
    price_percent: Mapped[float] = mapped_column(Float, nullable=False)

    # Счёт
    account_name: Mapped[str] = mapped_column(String(255), nullable=True)

    # Время записи
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        """Представление модели."""
        return f"<BondPriceHistory(figi={self.figi}, price={self.price_percent}%)>"


class SentAlert(Base):
    """Отправленные алерты (для anti-spam)."""

    __tablename__ = "sent_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    figi: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Тип алерта: 'drop_warning', 'drop_critical', 'rise_warning', 'rise_critical'
    alert_type: Mapped[str] = mapped_column(String(32), nullable=False)

    # Время отправки
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Количество отправленных алертов за день
    daily_count: Mapped[int] = mapped_column(Integer, default=1)

    def __repr__(self) -> str:
        """Представление модели."""
        return f"<SentAlert(figi={self.figi}, type={self.alert_type})>"
