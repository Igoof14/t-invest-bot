"""Сервис админской рассылки сообщений всем активным пользователям."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from features.users.repository import BotUserRepository

from .schemas import BroadcastResult

logger = logging.getLogger(__name__)

# Пауза между отправками: ~20 сообщений/сек, ниже лимита Telegram (~30/сек).
_SEND_DELAY = 0.05


class BroadcastService:
    """Рассылает сообщение всем активным пользователям.

    Шлёт копию исходного сообщения админа через ``copy_message`` — это
    сохраняет текст, форматирование и медиа без пометки «переслано».
    """

    def __init__(
        self,
        bot: Bot,
        *,
        repo: type[BotUserRepository] = BotUserRepository,
    ) -> None:
        """Инициализирует сервис ботом и репозиторием пользователей."""
        self._bot = bot
        self._repo = repo

    async def broadcast(self, from_chat_id: int, message_id: int) -> BroadcastResult:
        """Рассылает сообщение всем активным пользователям.

        Args:
            from_chat_id: Чат, откуда копировать сообщение (чат админа).
            message_id: ID сообщения для копирования.

        Returns:
            Сводка по доставке: доставлено, заблокировали, ошибок.

        """
        user_ids = await self._repo.get_all_active_users()
        delivered = blocked = failed = 0
        for user_id in user_ids:
            outcome = await self._send_one(user_id, from_chat_id, message_id)
            if outcome == "delivered":
                delivered += 1
            elif outcome == "blocked":
                blocked += 1
            else:
                failed += 1
            await asyncio.sleep(_SEND_DELAY)
        logger.info(
            "Рассылка завершена: доставлено=%d, заблокировали=%d, ошибок=%d",
            delivered,
            blocked,
            failed,
        )
        return BroadcastResult(delivered=delivered, blocked=blocked, failed=failed)

    async def _send_one(self, user_id: int, from_chat_id: int, message_id: int) -> str:
        """Отправляет копию одному пользователю.

        Returns:
            ``"delivered"``, ``"blocked"`` или ``"failed"``.

        """
        try:
            await self._bot.copy_message(
                chat_id=user_id, from_chat_id=from_chat_id, message_id=message_id
            )
            return "delivered"
        except TelegramForbiddenError:
            # Пользователь заблокировал или удалил бота — деактивируем.
            await self._repo.deactivate_user(user_id)
            return "blocked"
        except TelegramRetryAfter as e:
            # Флуд-контроль: ждём и пробуем ещё раз один раз.
            logger.warning("Флуд-контроль %d сек для %d", e.retry_after, user_id)
            await asyncio.sleep(e.retry_after)
            return await self._retry_once(user_id, from_chat_id, message_id)
        except TelegramBadRequest as e:
            logger.error("Не удалось отправить %d: %s", user_id, e)
            return "failed"

    async def _retry_once(self, user_id: int, from_chat_id: int, message_id: int) -> str:
        """Повторная попытка отправки после флуд-контроля."""
        try:
            await self._bot.copy_message(
                chat_id=user_id, from_chat_id=from_chat_id, message_id=message_id
            )
            return "delivered"
        except TelegramForbiddenError:
            await self._repo.deactivate_user(user_id)
            return "blocked"
        except TelegramBadRequest as e:
            logger.error("Повторная отправка %d не удалась: %s", user_id, e)
            return "failed"
