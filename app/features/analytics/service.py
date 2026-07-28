"""Публичный API продуктовой аналитики."""

import asyncio
import logging
import re
from typing import Any

from core.config import config

from .repository import AnalyticsRepository
from .schemas import Direction, EventName

logger = logging.getLogger(__name__)

# Сильные ссылки на фоновые задачи трекинга: asyncio хранит только слабые,
# и без этого множества задача может быть собрана GC до записи события.
_pending: set[asyncio.Task[None]] = set()

# Ключи props, которые нельзя писать ни при каких условиях: через текст
# сообщений проходит T-Invest токен пользователя (FSM waiting_for_token).
_FORBIDDEN_PROPS = frozenset({"text", "token", "message", "caption"})

_SOURCE_ALLOWED = re.compile(r"[^a-z0-9_-]")
_SOURCE_MAX_LEN = 64


def sanitize_source(payload: str | None) -> str | None:
    """Нормализует deep-link payload из ``t.me/bot?start=<payload>``.

    Payload задаёт кто угодно, поэтому он приводится к безопасному виду и
    хранится только как свойство события, никогда как имя колонки или часть
    запроса.

    Args:
        payload: Сырое значение ``CommandObject.args``.

    Returns:
        Нормализованный источник, ``"invalid"`` если payload был непустым, но
        не содержал допустимых символов, или ``None`` если payload отсутствует.

    """
    if not payload or not payload.strip():
        return None
    cleaned = _SOURCE_ALLOWED.sub("", payload.strip().lower())[:_SOURCE_MAX_LEN]
    return cleaned or "invalid"


async def track(
    event: EventName,
    *,
    telegram_id: int | None = None,
    action: str | None = None,
    direction: Direction = Direction.IN,
    latency_ms: int | None = None,
    **props: Any,
) -> None:
    """Записывает продуктовое событие.

    Единственная точка входа: её используют и мидлварь, и явные вызовы из
    хендлеров. Никогда не бросает исключений — сбой аналитики не должен
    ломать пользовательский сценарий.

    Args:
        event: Имя события из ``EventName``.
        telegram_id: Пользователь, к которому относится событие.
        action: Нормализованная идентичность действия (callback_data, имя
            команды, текст кнопки).
        direction: ``IN`` для действий пользователя, ``OUT`` для отправок бота.
        latency_ms: Время обработки апдейта в миллисекундах.
        **props: Дополнительные свойства. Только JSON-сериализуемые скаляры.

    """
    try:
        if not config.analytics_enabled:
            return
        if telegram_id is not None and telegram_id == config.admin_id:
            # Действия админа (/broadcast, тестовые прожатия) исказили бы
            # воронку и отчёт по использованию фич.
            if not config.analytics_track_admin:
                return

        clean = {k: v for k, v in props.items() if v is not None and k not in _FORBIDDEN_PROPS}
        if len(clean) != len({k: v for k, v in props.items() if v is not None}):
            logger.warning(f"Из props события {event} удалены запрещённые ключи")

        await AnalyticsRepository.add_event(
            str(event),
            direction=str(direction),
            telegram_id=telegram_id,
            action=action[:128] if action else None,
            latency_ms=latency_ms,
            props=clean,
        )
    except Exception as e:
        # Осознанно глушим всё: единственное место в проекте, где потеря
        # данных предпочтительнее сломанного хендлера.
        logger.warning(f"Сбой трекинга события {event}: {e}")


def track_bg(event: EventName, **kwargs: Any) -> None:
    """Планирует запись события, не дожидаясь её.

    Версия ``track()`` для горячего пути: на пользовательских сценариях
    ответ бота не должен ждать похода в БД за аналитикой. Аргументы те же,
    что у ``track()``.

    Исключения не пробрасываются: ``track()`` гасит их внутри себя.
    """
    task = asyncio.create_task(track(event, **kwargs))
    _pending.add(task)
    task.add_done_callback(_pending.discard)


async def flush_tracking(timeout: float = 5.0) -> None:
    """Дожидается фоновых задач трекинга (вызывается при остановке сервиса).

    Args:
        timeout: Сколько секунд ждать. По истечении незавершённые события
            теряются — это предпочтительнее зависшей остановки.

    """
    if not _pending:
        return
    _, pending = await asyncio.wait(set(_pending), timeout=timeout)
    if pending:
        logger.warning(f"Не дописано событий аналитики: {len(pending)}")
