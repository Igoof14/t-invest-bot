"""Доступ к пользователям бота — через API бэкенда.

Таблицей `bot_users` владеет и пишет в неё только `bondelo-backend`, поэтому здесь
не осталось ни модели, ни SQL. Сигнатуры сохранены с тех времён, когда репозиторий
ходил в БД напрямую: вызывающий код от переезда не поменялся.

Контракт на ошибки тоже прежний: сетевой сбой или отказ бэкенда не роняют хендлер,
а превращаются в «ничего не вышло» (False/None/пустой список). Исключение —
:meth:`BotUserRepository.register_and_get_state`: на `/start` без регистрации
показывать нечего, и ошибку ловит уже сам хендлер.

Добавление и удаление токена бот больше не делает сам — это переехало в мини-апп
(`features/miniapp/api.py`), который ходит в `core.clients.backend.users` напрямую.
"""

import logging

from common.brokers import Broker
from core.clients.backend import users as users_api
from core.clients.backend.errors import BackendError

logger = logging.getLogger(__name__)


class BotUserRepository:
    """Пользователи бота. Все методы ходят в бэкенд по HTTP."""

    @classmethod
    async def register_and_get_state(
        cls,
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> tuple[bool, bool]:
        """Регистрирует пользователя и возвращает его состояние.

        Returns:
            Кортеж ``(is_new_user, has_token)``.

        Raises:
            BackendError: Бэкенд недоступен или вернул ошибку.

        """
        registration = await users_api.register(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )
        logger.info(
            f"Пользователь {telegram_id}: новый={registration.is_new_user}, "
            f"есть_токен={registration.has_token}"
        )
        return registration.is_new_user, registration.has_token

    @classmethod
    async def get_token_by_telegram_id(
        cls, telegram_id: int, broker: Broker = Broker.TINVEST
    ) -> str | None:
        """Достает токен пользователя по телеграм id."""
        try:
            token = await users_api.get_token(telegram_id, broker)
        except BackendError as e:
            logger.error(f"Ошибка при получении токена для пользователя {telegram_id}: {e}")
            return None
        logger.debug(f"Токен пользователя {telegram_id}: {'найден' if token else 'не найден'}")
        return token or None

    @classmethod
    async def get_all_active_users(cls) -> list[int]:
        """Возвращает список telegram_id всех активных пользователей."""
        try:
            return await users_api.list_active()
        except BackendError as e:
            logger.error(f"Ошибка при получении активных пользователей: {e}")
            return []

    @classmethod
    async def deactivate_user(cls, telegram_id: int) -> bool:
        """Деактивирует пользователя (помечает как неактивного)."""
        try:
            await users_api.deactivate(telegram_id)
        except BackendError as e:
            logger.error(f"Ошибка при деактивации пользователя {telegram_id}: {e}")
            return False
        logger.info(f"Деактивирован пользователь: {telegram_id}")
        return True
