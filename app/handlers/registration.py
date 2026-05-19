"""Модуль для регистрации всех обработчиков бота."""

import logging

from aiogram import Bot, Dispatcher, F
from core.enums import (
    CouponCallbackData,
    PriceAlertCallbackData,
    SettingsCallbackData,
)

from .coupon_handlers import CouponHandler
from .price_alert_handlers import PriceAlertSettingsHandler, ThresholdStates
from .setting_handlers import (
    SettingHandler,
    TokenStates,
)

logger = logging.getLogger(__name__)


def register_handlers(dp: Dispatcher, bot: Bot) -> None:
    """Регистрация всех обработчиков бота.

    Args:
        dp: Диспетчер бота
        bot: Экземпляр бота

    """
    # Обработчики кнопок основной клавиатуры

    # Обработчики callback-кнопок для купонов
    callback_values = {
        CouponCallbackData.COUPONS_TODAY.value,
        CouponCallbackData.COUPONS_WEEK.value,
        CouponCallbackData.COUPONS_MONTH.value,
    }
    dp.callback_query.register(CouponHandler.handle_coupon_request, F.data.in_(callback_values))

    # Обработчики callback-кнопок для настроек
    callback_values = {
        SettingsCallbackData.ADD_TOKEN.value,
        SettingsCallbackData.RM_TOKEN.value,
    }
    dp.callback_query.register(SettingHandler.handle_settings, F.data.in_(callback_values))
    dp.message.register(SettingHandler.handle_token_message, TokenStates.waiting_for_token)
    dp.message.register(
        SettingHandler.handle_delete_confirmation, TokenStates.waiting_for_delete_confirmation
    )

    # Обработчики уведомлений о ценах
    dp.callback_query.register(
        PriceAlertSettingsHandler.handle_price_alerts_menu,
        F.data == PriceAlertCallbackData.PRICE_ALERTS_SETTINGS.value,
    )
    dp.callback_query.register(
        PriceAlertSettingsHandler.handle_toggle_alerts,
        F.data == PriceAlertCallbackData.PRICE_ALERTS_TOGGLE.value,
    )
    dp.callback_query.register(
        PriceAlertSettingsHandler.handle_thresholds_menu,
        F.data == PriceAlertCallbackData.PRICE_ALERTS_SETTINGS.value + "_thresholds",
    )

    # Обработчики выбора порогов
    threshold_callbacks = {
        PriceAlertCallbackData.PRICE_ALERTS_DROP_WARNING.value,
        PriceAlertCallbackData.PRICE_ALERTS_DROP_CRITICAL.value,
        PriceAlertCallbackData.PRICE_ALERTS_RISE_WARNING.value,
        PriceAlertCallbackData.PRICE_ALERTS_RISE_CRITICAL.value,
    }
    dp.callback_query.register(
        PriceAlertSettingsHandler.handle_threshold_select, F.data.in_(threshold_callbacks)
    )

    # Обработчики ввода порогов
    dp.message.register(
        PriceAlertSettingsHandler.handle_threshold_input, ThresholdStates.waiting_for_drop_warning
    )
    dp.message.register(
        PriceAlertSettingsHandler.handle_threshold_input, ThresholdStates.waiting_for_drop_critical
    )
    dp.message.register(
        PriceAlertSettingsHandler.handle_threshold_input, ThresholdStates.waiting_for_rise_warning
    )
    dp.message.register(
        PriceAlertSettingsHandler.handle_threshold_input, ThresholdStates.waiting_for_rise_critical
    )

    logger.info("Все обработчики успешно зарегистрированы")
