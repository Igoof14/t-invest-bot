"""Модели фичи рейтингов: подписки пользователей и состояние дедупа релизов."""

from datetime import date, datetime

from core.database import Base
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
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

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    def __repr__(self) -> str:
        """Представление модели."""
        return (
            f"<RatingAlertSettings(telegram_id={self.telegram_id}, "
            f"agency={self.agency}, enabled={self.alerts_enabled})>"
        )


class RatingRelease(Base):
    """Увиденный релиз рейтинга (состояние дедупа полинга).

    Единая таблица на всех провайдеров: одна строка на пару (agency, uid).
    """

    __tablename__ = "rating_releases"
    __table_args__ = (UniqueConstraint("agency", "uid", name="uq_rating_releases_agency_uid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agency: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    # Стабильный идентификатор релиза у агентства (post id / slug).
    uid: Mapped[str] = mapped_column(String(128), nullable=False)

    url: Mapped[str] = mapped_column(Text, nullable=False)
    release_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    inn: Mapped[str | None] = mapped_column(String(12), nullable=True, index=True)
    isins: Mapped[str | None] = mapped_column(Text, nullable=True)

    entity_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(255), nullable=True)

    rating_action: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rating_value: Mapped[str | None] = mapped_column(String(64), nullable=True)
    outlook: Mapped[str | None] = mapped_column(String(64), nullable=True)

    publication_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # ISO-строка сигнала изменения (для агентств, где релизы меняются).
    modified: Mapped[str | None] = mapped_column(String(32), nullable=True)

    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        """Представление модели."""
        return f"<RatingRelease(agency={self.agency}, uid={self.uid}, inn={self.inn})>"
