"""Модуль для регистрации всех обработчиков бота."""

import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from core.enums import ButtonTexts, CallbackData

from .base_handlers import (
    handle_coupons_button,
    handle_help_button,
    handle_maturities_button,
    handle_monitoring_button,
    handle_my_reports_button,
    handle_offers_button,
    handle_settings_button,
    start_handler,
)
from .coupon_handlers import CouponHandler
from .setting_handlers import AlertSettingsHandler, SettingHandler, ThresholdStates, TokenStates

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
    dp.message.register(handle_maturities_button, F.text == ButtonTexts.MATURITIES.value)
    dp.message.register(handle_offers_button, F.text == ButtonTexts.OFFERS.value)
    dp.message.register(handle_help_button, F.text == ButtonTexts.HELP.value)
    dp.message.register(handle_my_reports_button, F.text == ButtonTexts.MY_REPORTS.value)
    dp.message.register(handle_monitoring_button, F.text == ButtonTexts.MONITORING.value)
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
    dp.message.register(
        SettingHandler.handle_delete_confirmation, TokenStates.waiting_for_delete_confirmation
    )

    # Обработчики уведомлений о ценах
    dp.callback_query.register(
        AlertSettingsHandler.handle_price_alerts_menu,
        F.data == CallbackData.PRICE_ALERTS_SETTINGS.value,
    )
    dp.callback_query.register(
        AlertSettingsHandler.handle_toggle_alerts,
        F.data == CallbackData.PRICE_ALERTS_TOGGLE.value,
    )
    dp.callback_query.register(
        AlertSettingsHandler.handle_thresholds_menu,
        F.data == CallbackData.PRICE_ALERTS_SETTINGS.value + "_thresholds",
    )

    # Обработчики выбора порогов
    threshold_callbacks = {
        CallbackData.PRICE_ALERTS_DROP_WARNING.value,
        CallbackData.PRICE_ALERTS_DROP_CRITICAL.value,
        CallbackData.PRICE_ALERTS_RISE_WARNING.value,
        CallbackData.PRICE_ALERTS_RISE_CRITICAL.value,
    }
    dp.callback_query.register(
        AlertSettingsHandler.handle_threshold_select, F.data.in_(threshold_callbacks)
    )

    # Обработчики ввода порогов
    dp.message.register(
        AlertSettingsHandler.handle_threshold_input, ThresholdStates.waiting_for_drop_warning
    )
    dp.message.register(
        AlertSettingsHandler.handle_threshold_input, ThresholdStates.waiting_for_drop_critical
    )
    dp.message.register(
        AlertSettingsHandler.handle_threshold_input, ThresholdStates.waiting_for_rise_warning
    )
    dp.message.register(
        AlertSettingsHandler.handle_threshold_input, ThresholdStates.waiting_for_rise_critical
    )

    logger.info("Все обработчики успешно зарегистрированы")
