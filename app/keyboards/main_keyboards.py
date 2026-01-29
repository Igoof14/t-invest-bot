"""Основные клавиатуры для бота."""

from aiogram.types import InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from core.enums import ButtonTexts, CallbackData


class KeyboardHelper:
    """Хелпер для создания клавиатур."""

    @staticmethod
    def create_coupons_inline_keyboard() -> InlineKeyboardBuilder:
        """Создает инлайн клавиатуру для выбора периода купонов."""
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(
                text=ButtonTexts.TODAY.value,
                callback_data=CallbackData.COUPONS_TODAY.value,
            )
        )
        builder.add(
            InlineKeyboardButton(
                text=ButtonTexts.WEEK.value,
                callback_data=CallbackData.COUPONS_WEEK.value,
            )
        )
        builder.add(
            InlineKeyboardButton(
                text=ButtonTexts.MONTH.value,
                callback_data=CallbackData.COUPONS_MONTH.value,
            )
        )
        return builder

    @staticmethod
    def create_settings_keyboard() -> InlineKeyboardBuilder:
        """Создает инлайн клавиатуру для настроек."""
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(
                text=ButtonTexts.ADD_TOKEN.value,
                callback_data=CallbackData.ADD_TOKEN.value,
            )
        )
        builder.add(
            InlineKeyboardButton(
                text=ButtonTexts.RM_TOKEN.value,
                callback_data=CallbackData.RM_TOKEN.value,
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
            ButtonTexts.ALERTS_OFF.value if alerts_enabled else ButtonTexts.ALERTS_ON.value
        )
        builder.add(
            InlineKeyboardButton(
                text=toggle_text,
                callback_data=CallbackData.PRICE_ALERTS_TOGGLE.value,
            )
        )

        # Кнопка настройки порогов (только если уведомления включены)
        if alerts_enabled:
            builder.add(
                InlineKeyboardButton(
                    text=ButtonTexts.ALERTS_SETTINGS.value,
                    callback_data=CallbackData.PRICE_ALERTS_SETTINGS.value + "_thresholds",
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
                text="Падение Warning",
                callback_data=CallbackData.PRICE_ALERTS_DROP_WARNING.value,
            )
        )
        builder.add(
            InlineKeyboardButton(
                text="Падение Critical",
                callback_data=CallbackData.PRICE_ALERTS_DROP_CRITICAL.value,
            )
        )
        builder.add(
            InlineKeyboardButton(
                text="Рост Warning",
                callback_data=CallbackData.PRICE_ALERTS_RISE_WARNING.value,
            )
        )
        builder.add(
            InlineKeyboardButton(
                text="Рост Critical",
                callback_data=CallbackData.PRICE_ALERTS_RISE_CRITICAL.value,
            )
        )
        builder.add(
            InlineKeyboardButton(
                text=ButtonTexts.BACK_TO_SETTINGS.value,
                callback_data=CallbackData.PRICE_ALERTS_SETTINGS.value,
            )
        )

        builder.adjust(2, 2, 1)
        return builder

    @staticmethod
    def create_main_keyboard() -> ReplyKeyboardMarkup:
        """Создает основную клавиатуру с кнопками."""
        return ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text=ButtonTexts.COUPONS.value),
                    KeyboardButton(text=ButtonTexts.MATURITIES.value),
                    KeyboardButton(text=ButtonTexts.OFFERS.value),
                ],
                [
                    KeyboardButton(text=ButtonTexts.MONITORING.value),
                    KeyboardButton(text=ButtonTexts.SETTINGS.value),
                    KeyboardButton(text=ButtonTexts.HELP.value),
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
                [KeyboardButton(text=ButtonTexts.SETTINGS.value)],
                [KeyboardButton(text=ButtonTexts.HELP.value)],
            ],
            resize_keyboard=True,
            one_time_keyboard=False,
        )
