"""Основные клавиатуры бота."""

from aiogram.types import InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from core.enums import (
    CouponButtonTexts,
    CouponCallbackData,
    MainKeyboardButtonTexts,
    OfferCallbackData,
    PriceAlertButtonTexts,
    PriceAlertCallbackData,
    SettingsButtonTexts,
    SettingsCallbackData,
)


class KeyboardHelper:
    """Хелпер для создания клавиатур."""

    @staticmethod
    def create_coupons_inline_keyboard() -> InlineKeyboardBuilder:
        """Создает инлайн клавиатуру для выбора периода купонов."""
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(
                text=CouponButtonTexts.TODAY.value,
                callback_data=CouponCallbackData.COUPONS_TODAY.value,
            )
        )
        builder.add(
            InlineKeyboardButton(
                text=CouponButtonTexts.WEEK.value,
                callback_data=CouponCallbackData.COUPONS_WEEK.value,
            )
        )
        builder.add(
            InlineKeyboardButton(
                text=CouponButtonTexts.MONTH.value,
                callback_data=CouponCallbackData.COUPONS_MONTH.value,
            )
        )
        return builder

    @staticmethod
    def create_settings_keyboard() -> InlineKeyboardBuilder:
        """Создает инлайн клавиатуру для настроек."""
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(
                text=SettingsButtonTexts.ADD_TOKEN.value,
                callback_data=SettingsCallbackData.ADD_TOKEN.value,
            )
        )
        builder.add(
            InlineKeyboardButton(
                text=SettingsButtonTexts.RM_TOKEN.value,
                callback_data=SettingsCallbackData.RM_TOKEN.value,
            )
        )
        builder.adjust(2)

        return builder

    @staticmethod
    def create_price_alerts_keyboard(alerts_enabled: bool) -> InlineKeyboardBuilder:
        """Создает инлайн клавиатуру для настроек уведомлений о ценах.

        Args:
            alerts_enabled: Включены ли уведомления

        """
        builder = InlineKeyboardBuilder()

        # Кнопка вкл/выкл
        toggle_text = (
            PriceAlertButtonTexts.ALERTS_OFF.value
            if alerts_enabled
            else PriceAlertButtonTexts.ALERTS_ON.value
        )
        builder.add(
            InlineKeyboardButton(
                text=toggle_text,
                callback_data=PriceAlertCallbackData.PRICE_ALERTS_TOGGLE.value,
            )
        )

        # Кнопка настройки порогов (только если уведомления включены)
        if alerts_enabled:
            builder.add(
                InlineKeyboardButton(
                    text=PriceAlertButtonTexts.ALERTS_SETTINGS.value,
                    callback_data=PriceAlertCallbackData.PRICE_ALERTS_SETTINGS.value
                    + "_thresholds",
                )
            )

        builder.adjust(1)
        return builder

    @staticmethod
    def create_thresholds_keyboard() -> InlineKeyboardBuilder:
        """Создает клавиатуру для настройки порогов уведомлений."""
        builder = InlineKeyboardBuilder()

        builder.add(
            InlineKeyboardButton(
                text="Падение умеренное",
                callback_data=PriceAlertCallbackData.PRICE_ALERTS_DROP_WARNING.value,
            )
        )
        builder.add(
            InlineKeyboardButton(
                text="Рост умеренный",
                callback_data=PriceAlertCallbackData.PRICE_ALERTS_RISE_WARNING.value,
            )
        )

        builder.add(
            InlineKeyboardButton(
                text="Падение сильное",
                callback_data=PriceAlertCallbackData.PRICE_ALERTS_DROP_CRITICAL.value,
            )
        )

        builder.add(
            InlineKeyboardButton(
                text="Рост сильный",
                callback_data=PriceAlertCallbackData.PRICE_ALERTS_RISE_CRITICAL.value,
            )
        )
        builder.add(
            InlineKeyboardButton(
                text=PriceAlertButtonTexts.BACK_TO_SETTINGS.value,
                callback_data=PriceAlertCallbackData.PRICE_ALERTS_SETTINGS.value,
            )
        )

        builder.adjust(2, 2, 1)
        return builder

    @staticmethod
    def create_main_keyboard() -> ReplyKeyboardMarkup:
        """Создает основную клавиатуру с кнопками."""
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=MainKeyboardButtonTexts.NOTIFICATIONS.value)],
                [
                    KeyboardButton(text=MainKeyboardButtonTexts.COUPONS.value),
                    KeyboardButton(text=MainKeyboardButtonTexts.MATURITIES.value),
                    KeyboardButton(text=MainKeyboardButtonTexts.OFFERS.value),
                ],
                [
                    KeyboardButton(text=MainKeyboardButtonTexts.PRICE.value),
                    KeyboardButton(text=MainKeyboardButtonTexts.SETTINGS.value),
                    KeyboardButton(text=MainKeyboardButtonTexts.HELP.value),
                ],
            ],
            resize_keyboard=True,
            one_time_keyboard=False,
        )

    @staticmethod
    def create_new_user_keyboard() -> ReplyKeyboardMarkup:
        """Создает клавиатуру для нового пользователя."""
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=MainKeyboardButtonTexts.SETTINGS.value)],
                [KeyboardButton(text=MainKeyboardButtonTexts.HELP.value)],
            ],
            resize_keyboard=True,
            one_time_keyboard=False,
        )

    @staticmethod
    def create_offer_alerts_keyboard(alerts_enabled: bool) -> InlineKeyboardBuilder:
        """Создает инлайн клавиатуру для настроек уведомлений об офертах.

        Args:
            alerts_enabled: Включены ли уведомления

        """
        builder = InlineKeyboardBuilder()

        # Кнопка вкл/выкл
        toggle_text = (
            PriceAlertButtonTexts.ALERTS_OFF.value
            if alerts_enabled
            else PriceAlertButtonTexts.ALERTS_ON.value
        )
        builder.add(
            InlineKeyboardButton(
                text=toggle_text,
                callback_data=OfferCallbackData.OFFER_TOGGLE.value,
            )
        )
        return builder
