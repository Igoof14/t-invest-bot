"""Доступ к состоянию полинга рейтингов НРА."""

from __future__ import annotations

import logging

from core.database import session_scope
from sqlalchemy import func, select

from .models import NraRelease
from .schemas import ChangeType, RatingEvent

logger = logging.getLogger(__name__)


class NraReleaseRepository:
    """CRUD и детекция изменений для увиденных релизов НРА."""

    @classmethod
    async def get_modified_map(cls) -> dict[int, str | None]:
        """Возвращает снимок ``{post_id: modified_iso}`` всех релизов.

        Используется как in-memory источник для классификации без обращения к
        БД в цикле.
        """
        try:
            async with session_scope() as session:
                result = await session.execute(select(NraRelease.post_id, NraRelease.modified))
                return {post_id: modified for post_id, modified in result.all()}
        except Exception as e:
            logger.error(f"Ошибка при получении снимка релизов НРА: {e}")
            return {}

    @classmethod
    async def count(cls) -> int:
        """Возвращает количество сохранённых релизов."""
        async with session_scope() as session:
            result = await session.execute(select(func.count()).select_from(NraRelease))
            return result.scalar_one()

    @classmethod
    async def upsert_many(cls, events: list[RatingEvent]) -> None:
        """Создаёт или обновляет релизы по ``post_id``.

        Изменённых релизов за один полл — единицы, поэтому обновляем по одной
        строке (портируемо между Postgres и SQLite).
        """
        if not events:
            return

        async with session_scope() as session:
            for event in events:
                result = await session.execute(
                    select(NraRelease).where(NraRelease.post_id == event.post_id)
                )
                release = result.scalar_one_or_none()

                if release is None:
                    release = NraRelease(post_id=event.post_id)
                    session.add(release)

                release.url = event.url
                release.release_id = event.release_id
                release.inn = event.inn
                release.isins = ", ".join(event.isins) if event.isins else None
                release.entity_name = event.entity_name
                release.entity_type = event.entity_type
                release.rating_action = event.rating_action
                release.rating_value = event.rating_value
                release.outlook = event.outlook
                release.publication_date = event.publication_date
                release.modified = event.modified.isoformat() if event.modified else None

            await session.commit()

    @staticmethod
    def classify(
        post_id: int, modified_iso: str | None, known: dict[int, str | None]
    ) -> ChangeType | None:
        """Классифицирует релиз относительно снимка ``known``.

        Args:
            post_id: WordPress post id релиза.
            modified_iso: ISO-строка ``modified`` из REST API.
            known: Снимок ``{post_id: modified_iso}`` из БД.

        Returns:
            ``NEW`` если релиз неизвестен, ``CHANGED`` если ``modified`` новее
            сохранённого, иначе ``None`` (актуальная версия уже есть).

        """
        if post_id not in known:
            return ChangeType.NEW
        if modified_iso is not None and modified_iso != known[post_id]:
            return ChangeType.CHANGED
        return None
