"""Модели фичи users.

Модели пользователя (`bot_users`) здесь больше нет: таблицей владеет и мигрирует
её `bondelo-backend`, бот работает с ней через `core.clients.backend.users`.
"""

from core.database import Base
from sqlalchemy import BigInteger, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column


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
