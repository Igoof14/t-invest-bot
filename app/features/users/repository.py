"""Модуль для управления пользователями с использованием SQLAlchemy."""

import logging
from datetime import UTC, datetime

from core.database import session_scope
from sqlalchemy import func, or_, select, update

from .models import User

logger = logging.getLogger(__name__)


class BotUserRepository:
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
        async with session_scope() as session:
            try:
                # Проверяем, существует ли пользователь в той же сессии
                result = await session.execute(select(User).where(User.telegram_id == telegram_id))
                existing_user = result.scalar_one_or_none()

                if existing_user:
                    # Обновляем последнюю активность в той же сессии
                    await session.execute(
                        update(User)
                        .where(User.telegram_id == telegram_id)
                        .values(last_activity=datetime.now(UTC), is_active=True)
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
                    last_activity=datetime.now(UTC),
                )

                session.add(user)
                await session.commit()

                logger.info(f"Добавлен новый пользователь: {telegram_id} ({username})")
                return True

            except Exception as e:
                await session.rollback()
                logger.error(f"Ошибка при добавлении пользователя {telegram_id}: {e}")
                raise e

    @classmethod
    async def register_and_get_state(
        cls,
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> tuple[bool, bool]:
        """Регистрирует пользователя и возвращает его состояние за одну сессию.

        Делает то же, что ``add_user()`` + ``has_token()``, но одним походом
        в БД: на ``/start`` это горячий путь, а каждая сессия — отдельное
        соединение из пула.

        Returns:
            Кортеж ``(is_new_user, has_token)``.

        """
        async with session_scope() as session:
            try:
                result = await session.execute(select(User).where(User.telegram_id == telegram_id))
                existing_user = result.scalar_one_or_none()

                if existing_user:
                    token = existing_user.tinvest_token
                    existing_user.last_activity = datetime.now(UTC)
                    existing_user.is_active = True
                    await session.commit()
                    logger.info(f"Обновлена активность пользователя: {telegram_id}")
                    return False, token is not None and token != ""

                session.add(
                    User(
                        telegram_id=telegram_id,
                        username=username,
                        first_name=first_name,
                        last_name=last_name,
                        last_activity=datetime.now(UTC),
                    )
                )
                await session.commit()
                logger.info(f"Добавлен новый пользователь: {telegram_id} ({username})")
                return True, False

            except Exception as e:
                await session.rollback()
                logger.error(f"Ошибка при регистрации пользователя {telegram_id}: {e}")
                raise e

    @classmethod
    async def get_user_by_telegram_id(cls, telegram_id: int) -> User | None:
        """Получает пользователя по telegram_id."""
        async with session_scope() as session:
            try:
                result = await session.execute(select(User).where(User.telegram_id == telegram_id))
                return result.scalar_one_or_none()
            except Exception as e:
                logger.error(f"Ошибка при получении пользователя {telegram_id}: {e}")
                return None

    @classmethod
    async def has_user(cls, telegram_id: int) -> bool:
        """Проверяет существование пользователя."""
        async with session_scope() as session:
            try:
                result = await session.execute(
                    select(User.id).where(User.telegram_id == telegram_id, User.is_active)
                )
                user_id = result.scalar_one_or_none()
                return user_id is not None
            except Exception as e:
                logger.error(f"Ошибка при проверке пользователя {telegram_id}: {e}")
                return False

    @classmethod
    async def has_token(cls, telegram_id: int) -> bool:
        """Проверяет наличие токена пользователя."""
        async with session_scope() as session:
            try:
                result = await session.execute(
                    select(User.tinvest_token).where(User.telegram_id == telegram_id)
                )
                token = result.scalar_one_or_none()
                has_valid_token = token is not None and token != ""
                logger.debug(f"Проверка токена для {telegram_id}: {has_valid_token}")
                return has_valid_token
            except Exception as e:
                logger.error(f"Ошибка при проверке токена пользователя {telegram_id}: {e}")
                return False

    @classmethod
    async def get_token_by_telegram_id(cls, telegram_id: int) -> str | None:
        """Достает токен пользователя по телеграм id."""
        async with session_scope() as session:
            try:
                result = await session.execute(
                    select(User.tinvest_token).where(User.telegram_id == telegram_id)
                )
                token = result.scalar_one_or_none()
                logger.debug(
                    f"Токен пользователя {telegram_id}: {'найден' if token else 'не найден'}"
                )
                return token
            except Exception as e:
                logger.error(f"Ошибка при получении токена для пользователя {telegram_id}: {e}")
                return None

    @classmethod
    async def add_token(cls, telegram_id: int, token: str) -> bool:
        """Добавляет токен пользователя в базу данных."""
        async with session_scope() as session:
            try:
                result = await session.execute(
                    update(User).where(User.telegram_id == telegram_id).values(tinvest_token=token)
                )
                await session.commit()
                affected = getattr(result, "rowcount", 0)
                if affected > 0:
                    logger.info(f"Токен добавлен для пользователя {telegram_id}")
                    return True
                logger.warning(f"Пользователь {telegram_id} не найден при добавлении токена")
                return False
            except Exception as e:
                logger.error(f"Ошибка при добавлении токена пользователя {telegram_id}: {e}")
                await session.rollback()
                return False

    @classmethod
    async def remove_token(cls, telegram_id: int) -> bool:
        """Удаляет токен пользователя из базы данных."""
        async with session_scope() as session:
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

    @classmethod
    async def get_all_active_users(cls) -> list[int]:
        """Возвращает список telegram_id всех активных пользователей."""
        async with session_scope() as session:
            try:
                result = await session.execute(select(User.telegram_id).where(User.is_active))
                return list(result.scalars().all())
            except Exception as e:
                logger.error(f"Ошибка при получении активных пользователей: {e}")
                return []

    @classmethod
    async def get_user_count(cls) -> int:
        """Возвращает количество активных пользователей."""
        async with session_scope() as session:
            try:
                result = await session.execute(select(func.count(User.id)).where(User.is_active))
                return result.scalar() or 0
            except Exception as e:
                logger.error(f"Ошибка при подсчете пользователей: {e}")
                return 0

    @classmethod
    async def update_last_activity(cls, telegram_id: int) -> bool:
        """Обновляет время последней активности пользователя."""
        async with session_scope() as session:
            try:
                result = await session.execute(
                    update(User)
                    .where(User.telegram_id == telegram_id)
                    .values(last_activity=datetime.now(UTC))
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

    @classmethod
    async def touch_last_activity_if_stale(cls, telegram_id: int) -> bool:
        """Двигает ``last_activity``, если она ещё не обновлялась сегодня.

        Вызывается на каждый апдейт из аналитической мидлвари, поэтому
        сделана условной: один UPDATE в сутки на пользователя вместо
        записи на каждое нажатие кнопки. Без предварительного SELECT —
        условие целиком в WHERE.

        Returns:
            True, если время активности было обновлено.

        """
        now = datetime.now(UTC)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        try:
            async with session_scope() as session:
                result = await session.execute(
                    update(User)
                    .where(
                        User.telegram_id == telegram_id,
                        or_(User.last_activity.is_(None), User.last_activity < day_start),
                    )
                    .values(last_activity=now)
                )
                await session.commit()
                return getattr(result, "rowcount", 0) > 0
        except Exception as e:
            logger.warning(f"Не удалось обновить активность {telegram_id}: {e}")
            return False

    @classmethod
    async def deactivate_user(cls, telegram_id: int) -> bool:
        """Деактивирует пользователя (помечает как неактивного)."""
        async with session_scope() as session:
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
