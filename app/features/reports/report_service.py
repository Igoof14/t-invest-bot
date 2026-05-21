"""Сервис для рассылки отчётов пользователям."""

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from common.utils.datetime_utils import DateTimeHelper
from core.clients.t_invest.bonds import get_coupon_payment
from core.enums import ReportType

from ..users.repository import BotUserRepository

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
        user_count = await BotUserRepository.get_user_count()
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

            blocked_users = []
            all_users = await BotUserRepository.get_all_active_users()
            successful_sends = 0

            for uid in all_users:
                try:
                    coupon_data = await get_coupon_payment(
                        telegram_id=uid, start_datetime=start_datetime
                    )

                    if not coupon_data or not coupon_data.accounts:
                        continue

                    text = (
                        "".join(
                            f"{key}: {value:,.0f} ₽\n"
                            for key, value in coupon_data.accounts.items()
                        )
                        + f"\nИтого: {coupon_data.total_amount:,.0f} ₽"
                    )

                    await bot.send_message(uid, text, parse_mode="HTML")
                    successful_sends += 1
                except TelegramForbiddenError:
                    logger.warning(f"Бот заблокирован пользователем {uid}, деактивируем")
                    blocked_users.append(uid)
                except Exception as e:
                    logger.error(f"Ошибка при отправке пользователю {uid}: {e}")

            # Деактивируем только пользователей, заблокировавших бота
            for uid in blocked_users:
                await BotUserRepository.deactivate_user(uid)

            logger.info(f"Отчет '{report_type.value}' отправлен {successful_sends} пользователям")

            if blocked_users:
                logger.warning(f"Деактивировано {len(blocked_users)} заблокировавших бота")

        except Exception as e:
            logger.error(f"Ошибка при рассылке отчета: {e}")
