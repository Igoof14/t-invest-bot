"""Модель состояния полинга рейтингов НРА."""

from datetime import date, datetime

from core.database import Base
from sqlalchemy import BigInteger, Date, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column


class NraRelease(Base):
    """Увиденный релиз рейтинга НРА.

    Хранит состояние дедупликации полинга: по ``modified`` определяется,
    появилось ли новое или изменённое рейтинговое событие.
    """

    __tablename__ = "rating_nra_releases"

    # Стабильный WordPress post id релиза.
    post_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)

    # Свободный текст — без ограничения длины, чтобы исключить усечение.
    url: Mapped[str] = mapped_column(Text, nullable=False)
    release_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    inn: Mapped[str | None] = mapped_column(String(12), nullable=True, index=True)
    # Релиз может покрывать несколько выпусков — храним ISIN-ы через запятую.
    isins: Mapped[str | None] = mapped_column(Text, nullable=True)

    entity_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(255), nullable=True)

    rating_action: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rating_value: Mapped[str | None] = mapped_column(String(64), nullable=True)
    outlook: Mapped[str | None] = mapped_column(String(64), nullable=True)

    publication_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # ISO-строка из REST API НРА — сигнал изменения.
    modified: Mapped[str | None] = mapped_column(String(32), nullable=True)

    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        """Представление модели."""
        return f"<NraRelease(post_id={self.post_id}, inn={self.inn})>"
