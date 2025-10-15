"""Модуль для регистрации всех обработчиков бота."""

import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from core.enums import ButtonTexts, CallbackData

from .base_handlers import (
    handle_coupons_button,
    handle_help_button,
    handle_my_reports_button,
    handle_settings_button,
    start_handler,
)
from .coupon_handlers import CouponHandler
from .setting_handlers import SettingHandler, TokenStates

logger = logging.getLogger(__name__)


def register_handlers(dp: Dispatcher, bot: Bot) -> None:
    """Регистрация всех обработчиков бота.

    Args:
        dp: Диспетчер бота
        bot: Экземпляр бота

    """
    # Обработчики команд
    dp.message.register(start_handler, Command("start"))

    # Обработчики кнопок основной клавиатуры
    dp.message.register(handle_coupons_button, F.text == ButtonTexts.COUPONS.value)
    dp.message.register(handle_help_button, F.text == ButtonTexts.HELP.value)
    dp.message.register(handle_my_reports_button, F.text == ButtonTexts.MY_REPORTS.value)
    dp.message.register(handle_settings_button, F.text == ButtonTexts.SETTINGS.value)

    # Обработчики callback-кнопок для купонов
    callback_values = {
        CallbackData.COUPONS_TODAY.value,
        CallbackData.COUPONS_WEEK.value,
        CallbackData.COUPONS_MONTH.value,
    }
    dp.callback_query.register(CouponHandler.handle_coupon_request, F.data.in_(callback_values))

    # Обработчики callback-кнопок для настроек
    callback_values = {
        CallbackData.ADD_TOKEN.value,
        CallbackData.RM_TOKEN.value,
    }
    dp.callback_query.register(SettingHandler.handle_settings, F.data.in_(callback_values))
    dp.message.register(SettingHandler.handle_token_message, TokenStates.waiting_for_token)

    logger.info("Все обработчики успешно зарегистрированы")
