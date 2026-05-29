"""Утилиты для работы с ботом."""

import logging

from aiogram import Bot
from aiogram.types import BotCommand

logger = logging.getLogger(__name__)


def pluralize_days(n: int) -> str:
    """Возвращает слово «день» в правильном падеже для числа n.

    Args:
        n: Количество дней.

    Returns:
        «день», «дня» или «дней».

    Examples:
        1 → день, 2 → дня, 5 → дней, 11 → дней, 21 → день
    """
    if 11 <= n % 100 <= 19:
        return "дней"
    rem = n % 10
    if rem == 1:
        return "день"
    if 2 <= rem <= 4:
        return "дня"
    return "дней"


class BotUtils:
    """Утилиты для настройки бота."""

    @staticmethod
    async def set_commands(bot: Bot) -> None:
        """Установка команд бота.

        Args:
            bot: Экземпляр бота

        """
        commands = [
            BotCommand(command="start", description="Запустить бота"),
        ]

        try:
            await bot.set_my_commands(commands)
            logger.info("Команды бота успешно установлены")
        except Exception as e:
            logger.error(f"Ошибка при установке команд бота: {e}")
