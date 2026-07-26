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


def pluralize_bonds(n: int) -> str:
    """Возвращает слово «облигация» в правильном падеже для числа n.

    Args:
        n: Количество облигаций.

    Returns:
        «облигация», «облигации» или «облигаций».

    Examples:
        1 → облигация, 2 → облигации, 5 → облигаций, 11 → облигаций

    """
    if 11 <= n % 100 <= 19:
        return "облигаций"
    rem = n % 10
    if rem == 1:
        return "облигация"
    if 2 <= rem <= 4:
        return "облигации"
    return "облигаций"


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

    @staticmethod
    async def set_descriptions(bot: Bot) -> None:
        """Устанавливает описание бота для экрана до нажатия «Старт».

        ``description`` показывается на пустом экране чата с кнопкой «Старт»,
        ``short_description`` — в профиле бота и превью.

        Args:
            bot: Экземпляр бота.

        """
        description = (
            "Bondelo следит за вашим облигационным портфелем и предупреждает "
            "о проблемах раньше, чем они ударят по деньгам:\n\n"
            "• Аномальные движения цен.\n"
            "• Задержки купонов (сверка с НРД).\n"
            "• Изменения рейтингов.\n"
            "• Блокировки счетов эмитентов ФНС.\n"
            "• Напоминания об офертах и погашениях.\n"
            "• Отчёты по купонному доходу.\n\n"
            "Подключение — Read-only токен T-Invest. Нажмите «Старт» 👇"
        )
        short_description = (
            "Следит за облигациями: цены, купоны, рейтинги, оферты, "
            "блокировки эмитентов. Сигналы о проблемах раньше всех."
        )
        try:
            await bot.set_my_description(description=description)
            await bot.set_my_short_description(short_description=short_description)
            logger.info("Описание бота успешно установлено")
        except Exception as e:
            logger.error(f"Ошибка при установке описания бота: {e}")
