"""Утилиты для работы с ботом."""

import logging

from aiogram import Bot
from aiogram.types import BotCommand

logger = logging.getLogger(__name__)


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
