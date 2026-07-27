"""Запись продуктовых событий в БД."""

import logging
from typing import Any

from core.database import session_scope

from .models import BotEvent

logger = logging.getLogger(__name__)


class AnalyticsRepository:
    """Доступ к таблице событий. Только запись — читаем SQL-ом снаружи."""

    @classmethod
    async def add_event(
        cls,
        event_name: str,
        *,
        direction: str,
        telegram_id: int | None = None,
        action: str | None = None,
        latency_ms: int | None = None,
        props: dict[str, Any] | None = None,
    ) -> bool:
        """Вставляет одно событие.

        Ошибку не пробрасывает: аналитика не должна ронять хендлер, который
        её вызвал. Вызывающий код узнаёт о проблеме из лога и ``False``.

        Returns:
            True, если событие записано.

        """
        try:
            async with session_scope() as session:
                session.add(
                    BotEvent(
                        telegram_id=telegram_id,
                        event_name=event_name,
                        action=action,
                        direction=direction,
                        latency_ms=latency_ms,
                        props=props or None,
                    )
                )
                await session.commit()
                return True
        except Exception as e:
            logger.warning(
                f"Не удалось записать событие {event_name} (action={action}, "
                f"telegram_id={telegram_id}): {e}"
            )
            return False
