"""Модуль для управления пользователями с использованием SQLAlchemy."""

import logging
from datetime import datetime

from core.database import get_session
from models.user import User
from sqlalchemy import func, select, update
from sqlalchemy.engine import CursorResult

logger = logging.getLogger(__name__)


class UserStorage:
    """Класс для управления пользователями через базу данных."""

    @classmethod
    async def add_user(
        cls,
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> bool:
        """Добавляет пользователя в базу данных."""
        async for session in get_session():
            try:
                # Проверяем, существует ли пользователь в той же сессии
                result = await session.execute(select(User).where(User.telegram_id == telegram_id))
                existing_user = result.scalar_one_or_none()

                if existing_user:
                    # Обновляем последнюю активность в той же сессии
                    await session.execute(
                        update(User)
                        .where(User.telegram_id == telegram_id)
                        .values(last_activity=datetime.utcnow())
                    )
                    await session.commit()
                    logger.info(f"Обновлена активность пользователя: {telegram_id}")
                    return False

                # Создаем нового пользователя
                user = User(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    last_activity=datetime.utcnow(),
                )

                session.add(user)
                await session.commit()

                logger.info(f"Добавлен новый пользователь: {telegram_id} ({username})")
                return True

            except Exception as e:
                await session.rollback()
                logger.error(f"Ошибка при добавлении пользователя {telegram_id}: {e}")
                raise e
        return False

    @classmethod
    async def get_user_by_telegram_id(cls, telegram_id: int) -> User | None:
        """Получает пользователя по telegram_id."""
        async for session in get_session():
            try:
                result = await session.execute(select(User).where(User.telegram_id == telegram_id))
                return result.scalar_one_or_none()
            except Exception as e:
                logger.error(f"Ошибка при получении пользователя {telegram_id}: {e}")
                return None

    @classmethod
    async def has_user(cls, telegram_id: int) -> bool:
        """Проверяет существование пользователя."""
        async for session in get_session():
            try:
                result = await session.execute(
                    select(User.id).where(User.telegram_id == telegram_id, User.is_active)
                )
                user_id = result.scalar_one_or_none()
                return user_id is not None
            except Exception as e:
                logger.error(f"Ошибка при проверке пользователя {telegram_id}: {e}")
                return False
        return False

    @classmethod
    async def has_token(cls, telegram_id: int) -> bool:
        """Проверяет наличие токена пользователя."""
        async for session in get_session():
            try:
                result = await session.execute(
                    select(User.tinvest_token).where(
                        User.telegram_id == telegram_id, User.tinvest_token.isnot(None)
                    )
                )
                logger.info(f"result: {result}")
                token = result.scalar_one_or_none()
                return token is not None
            except Exception as e:
                logger.error(f"Ошибка при проверке токена пользователя {telegram_id}: {e}")
                return False
        return False

    @classmethod
    async def add_token(cls, telegram_id: int, token: str) -> bool:
        """Добавляет токен пользователя в базу данных."""
        async for session in get_session():
            try:
                await session.execute(
                    update(User).where(User.telegram_id == telegram_id).values(tinvest_token=token)
                )
                await session.commit()
                return True
            except Exception as e:
                logger.error(f"Ошибка при добавлении токена пользователя {telegram_id}: {e}")
                await session.rollback()
                return False
        return False

    @classmethod
    async def remove_token(cls, telegram_id: int) -> bool:
        """Удаляет токен пользователя из базы данных."""
        async for session in get_session():
            try:
                await session.execute(
                    update(User).where(User.telegram_id == telegram_id).values(tinvest_token=None)
                )
                await session.commit()
                return True
            except Exception as e:
                logger.error(f"Ошибка при удалении токена пользователя {telegram_id}: {e}")
                await session.rollback()
                return False
        return False

    @classmethod
    async def get_all_active_users(cls) -> list[int]:
        """Возвращает список telegram_id всех активных пользователей."""
        result = []
        async for session in get_session():
            try:
                result = await session.execute(select(User.telegram_id).where(User.is_active))
                return list(result.scalars().all())
            except Exception as e:
                logger.error(f"Ошибка при получении активных пользователей: {e}")
                return []
        return []

    @classmethod
    async def get_user_count(cls) -> int:
        """Возвращает количество активных пользователей."""
        async for session in get_session():
            try:
                result = await session.execute(select(func.count(User.id)).where(User.is_active))
                return result.scalar() or 0
            except Exception as e:
                logger.error(f"Ошибка при подсчете пользователей: {e}")
                return 0
        return 0

    @classmethod
    async def update_last_activity(cls, telegram_id: int) -> bool:
        """Обновляет время последней активности пользователя."""
        async for session in get_session():
            try:
                result = await session.execute(
                    update(User)
                    .where(User.telegram_id == telegram_id)
                    .values(last_activity=datetime.utcnow())
                )
                await session.commit()

                affected = getattr(result, "rowcount", 0)
                if affected > 0:
                    logger.debug(f"Обновлена активность пользователя: {telegram_id}")
                    return True
                else:
                    logger.warning(
                        f"Пользователь {telegram_id} не найден для обновления активности"
                    )
                    return False

            except Exception as e:
                await session.rollback()
                logger.error(f"Ошибка при обновлении активности {telegram_id}: {e}")
                return False
        return False

    @classmethod
    async def deactivate_user(cls, telegram_id: int) -> bool:
        """Деактивирует пользователя (помечает как неактивного)."""
        async for session in get_session():
            try:
                result = await session.execute(
                    update(User).where(User.telegram_id == telegram_id).values(is_active=False)
                )
                await session.commit()

                affected = getattr(result, "rowcount", 0)
                if affected > 0:
                    logger.info(f"Деактивирован пользователь: {telegram_id}")
                    return True
                logger.warning(f"Пользователь {telegram_id} не найден для деактивации")
                return False

            except Exception as e:
                await session.rollback()
                logger.error(f"Ошибка при деактивации пользователя {telegram_id}: {e}")
                return False
        return False
