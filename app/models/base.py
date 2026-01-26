"""Базовые модели для SQLAlchemy."""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""

    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


# Импортируем все модели здесь, чтобы SQLAlchemy их видел при создании таблиц
try:
    from models.alerts import BondPriceHistory, SentAlert, UserAlertSettings
    from models.user import User

    # Добавляем все модели в список для явного экспорта
    __all__ = ["Base", "User", "UserAlertSettings", "BondPriceHistory", "SentAlert"]
except ImportError as e:
    # Если модель не может быть импортирована, логируем предупреждение
    import logging

    logger = logging.getLogger(__name__)
    logger.warning(f"Не удалось импортировать модели: {e}")
    __all__ = ["Base"]
