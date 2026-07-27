"""Модель продуктового события бота."""

from datetime import datetime
from typing import Any

from core.database import Base
from sqlalchemy import JSON, BigInteger, DateTime, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class BotEvent(Base):
    """Одно продуктовое событие. Таблица append-only: строки не обновляются.

    Схема совместима с последующей выгрузкой в BigQuery: ``id`` служит
    курсором экспорта, ``exported_at`` отмечает уже выгруженные строки.
    """

    __tablename__ = "bot_events"

    # Вариант Integer для SQLite: там BIGINT-первичный ключ не автоинкрементится,
    # а тесты создают схему на in-memory SQLite.
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Системные события могут быть не привязаны к пользователю.
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    event_name: Mapped[str] = mapped_column(String(64), nullable=False)
    # Нормализованная идентичность действия: callback_data, имя команды,
    # текст кнопки. Отдельной колонкой, а не в props, — чтобы воронки и
    # отчёт по использованию фич считались по индексу, без разбора JSON.
    action: Mapped[str | None] = mapped_column(String(128), nullable=True)
    direction: Mapped[str] = mapped_column(String(3), nullable=False)
    # JSON, а не JSONB напрямую: тесты используют in-memory SQLite,
    # где типа JSONB нет.
    props: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_bot_events_tg_occurred", "telegram_id", "occurred_at"),
        Index("ix_bot_events_name_occurred", "event_name", "occurred_at"),
        Index("ix_bot_events_occurred_at", "occurred_at"),
    )

    def __repr__(self) -> str:
        """Представление события для логов."""
        return f"<BotEvent({self.event_name}, action={self.action}, tg={self.telegram_id})>"
