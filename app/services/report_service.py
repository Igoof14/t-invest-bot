"""Сервис для рассылки отчётов пользователям."""

import logging

from aiogram import Bot
from aiogram.types import ChatIdUnion
from core.enums import ReportType
from invest.invest import get_coupon_payment
from storage import BotUserStorage
from utils.datetime_utils import DateTimeHelper

logger = logging.getLogger(__name__)


class ReportService:
    """Сервис для рассылки отчётов."""

    @staticmethod
    async def send_report(bot: Bot, report_type: ReportType) -> None:
        """Рассылка отчёта всем пользователям.

        Args:
            bot: Экземпляр бота
            report_type: Тип отчёта (дневной/недельный)

        """
        user_count = await BotUserStorage.get_user_count()
        if user_count == 0:
            logger.info("Нет пользователей для рассылки")
            return

        try:
            if report_type.value == "daily":
                start_datetime = DateTimeHelper.get_today_start()
            elif report_type.value == "weekly":
                start_datetime = DateTimeHelper.get_week_start()
            else:
                logger.error(f"Неизвестный тип отчета: {report_type.value}")
                return

            failed_users = []
            all_users = await BotUserStorage.get_all_active_users()

            for uid in all_users:
                try:
                    text = await get_coupon_payment(user_id=uid, start_datetime=start_datetime)
                    await bot.send_message(uid, text, parse_mode="HTML")
                except Exception as e:
                    logger.error(f"Ошибка при отправке пользователю {uid}: {e}")
                    failed_users.append(uid)

            # Деактивируем пользователей, которым не удалось отправить сообщение
            for uid in failed_users:
                await BotUserStorage.deactivate_user(uid)

            successful_sends = user_count - len(failed_users)
            logger.info(f"Отчет '{report_type.value}' отправлен {successful_sends} пользователям")

            if failed_users:
                logger.warning(f"Не удалось отправить {len(failed_users)} пользователям")

        except Exception as e:
            logger.error(f"Ошибка при рассылке отчета: {e}")
