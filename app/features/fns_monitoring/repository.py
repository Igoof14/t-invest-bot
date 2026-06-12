"""Доступ к ИНН эмитентов для проверки блокировок ФНС."""

from __future__ import annotations

import logging

from core.database import session_scope
from features.issuers.models import Issuer
from sqlalchemy import select

logger = logging.getLogger(__name__)


class FnsRepository:
    """Чтение ИНН эмитентов из реестра для проверки в ФНС."""

    @classmethod
    async def get_all_inns(cls) -> list[str]:
        """Возвращает список всех ненулевых ИНН эмитентов.

        Returns:
            Список ИНН строками.
        """
        async with session_scope() as session:
            result = await session.execute(
                select(Issuer.inn).where(Issuer.inn.is_not(None))
            )
            return [row for (row,) in result.all()]
