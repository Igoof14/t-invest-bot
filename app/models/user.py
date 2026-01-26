"""Модель пользователя."""

from datetime import datetime
from typing import Optional

from models.base import Base
from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column


class User(Base):
    """Модель пользователя бота."""

    __tablename__ = "bot_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tinvest_token: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Метаданные
    is_active: Mapped[bool] = mapped_column(default=True)
    is_bot: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_activity: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        """Представление модели пользователя."""
        return f"<User(telegram_id={self.telegram_id}, username={self.username})>"

    @property
    def full_name(self) -> str:
        """Полное имя пользователя."""
        parts = []
        if self.first_name:
            parts.append(self.first_name)
        if self.last_name:
            parts.append(self.last_name)
        return " ".join(parts) or self.username or f"User_{self.telegram_id}"


class TinvestUser(Base):
    """Модель пользователя т-ивестиций."""

    __tablename__ = "tinvest_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    prem_status: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    qual_status: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    qualified_for_work_with: Mapped[str | None] = mapped_column(Text, nullable=True)
    tariff: Mapped[str | None] = mapped_column(String(255), nullable=True)
    risk_level_code: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Метаданные
    # is_active: Mapped[bool] = mapped_column(default=True)
    # is_bot: Mapped[bool] = mapped_column(default=False)
    # created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # last_activity: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
