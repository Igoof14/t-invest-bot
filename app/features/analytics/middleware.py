"""Мидлварь автоматического трекинга входящих апдейтов."""

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.dispatcher.event.bases import UNHANDLED
from aiogram.types import CallbackQuery, Message, TelegramObject, Update
from core.config import config
from core.enums import MainKeyboardButtonTexts

from .schemas import Direction, EventName
from .service import track

logger = logging.getLogger(__name__)

_BUTTON_TEXTS = frozenset(item.value for item in MainKeyboardButtonTexts)


class AnalyticsMiddleware(BaseMiddleware):
    """Пишет событие в ``bot_events`` на каждый входящий апдейт.

    Регистрируется как ``dp.update.outer_middleware``: на уровне ``update``
    каждый апдейт учитывается ровно один раз, и видны апдейты, для которых
    вообще не нашлось хендлера, — это сигнал о тупиках в UX.

    Инвариант: любой сбой аналитики проглатывается. Исключение самого
    хендлера, напротив, пробрасывается дальше — мидлварь его только помечает.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """Выполняет хендлер и записывает событие о результате."""
        started = time.perf_counter()
        result: Any = UNHANDLED
        error = False
        try:
            result = await handler(event, data)
            return result
        except Exception:
            error = True
            raise
        finally:
            latency_ms = int((time.perf_counter() - started) * 1000)
            try:
                await self._record(
                    event,
                    matched=not error and result is not UNHANDLED,
                    error=error,
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"Сбой аналитической мидлвари: {e}")

    async def _record(
        self,
        event: TelegramObject,
        *,
        matched: bool,
        error: bool,
        latency_ms: int,
    ) -> None:
        """Классифицирует апдейт и пишет событие."""
        if not isinstance(event, Update):
            return

        inner = self._inner_event(event)
        telegram_id = getattr(getattr(inner, "from_user", None), "id", None)
        name, action, extra = self._classify(inner)

        await track(
            name,
            telegram_id=telegram_id,
            action=action,
            direction=Direction.IN,
            latency_ms=latency_ms,
            matched=matched,
            error=error or None,
            is_admin=True if telegram_id == config.admin_id else None,
            **extra,
        )

        if telegram_id is not None:
            # Отложенный импорт: features.users.handlers трекает события, то есть
            # импортирует эту фичу, — цикл analytics -> users -> analytics.
            from features.users.repository import BotUserRepository

            await BotUserRepository.touch_last_activity_if_stale(telegram_id)

    @staticmethod
    def _inner_event(update: Update) -> TelegramObject | None:
        """Возвращает вложенный объект апдейта или None для неизвестного типа."""
        try:
            return update.event
        except LookupError:
            # UpdateTypeLookupError — Telegram добавил тип, которого не знает
            # установленная версия aiogram.
            return None

    @staticmethod
    def _classify(inner: TelegramObject | None) -> tuple[EventName, str | None, dict[str, Any]]:
        """Определяет имя события, ``action`` и дополнительные props.

        Идентичность выводится из самого апдейта, а не из имени
        матчнувшегося хендлера: ``data["handler"]`` заполняется во внутренней
        цепочке роутера и на outer-мидлвари недоступен.
        """
        if isinstance(inner, CallbackQuery):
            return EventName.CALLBACK_CLICK, inner.data, {}

        if isinstance(inner, Message):
            text = inner.text or ""
            if text.startswith("/"):
                head, _, args = text[1:].partition(" ")
                command = head.split("@", 1)[0]
                return EventName.COMMAND, command, {"has_payload": bool(args.strip()) or None}
            if text in _BUTTON_TEXTS:
                return EventName.BUTTON_CLICK, text, {}
            # Текст сообщения не сохраняем: через него проходит T-Invest токен.
            return EventName.TEXT_MESSAGE, None, {"text_len": len(text)}

        return EventName.UPDATE_OTHER, type(inner).__name__ if inner else None, {}
