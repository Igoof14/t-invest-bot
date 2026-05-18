"""Обработчики внутри клавиатуры уведомлений."""

import logging
from datetime import UTC, datetime

from aiogram import F, Router
from aiogram.types import LinkPreviewOptions, Message
from core.enums import NotificationKeybordButtonTexts
from keyboards import KeyboardHelper
from storage.offer_alert.settings_repo import OfferSettingsRepository
from storage.price_alert import PriceAlertStorage

logger = logging.getLogger(__name__)

router: Router = Router()


@router.message(F.text == NotificationKeybordButtonTexts.BACK_TO_MAIN_KEYBORD.value)
async def handle_back_to_main_button(message: Message) -> None:
    """Обработка кнопки 'Назад'."""
    try:
        sent = await message.answer(
            "Главное меню:", reply_markup=KeyboardHelper.create_main_keyboard()
        )
        await message.delete()
    except Exception as e:
        logger.error(f"Ошибка при обработке кнопки 'Назад': {e}")
        await message.answer("Произошла ошибка")


@router.message(F.text == NotificationKeybordButtonTexts.OFFER_ALERT.value)
async def handle_notification_offer_alert_button(message: Message):
    """Обработка кнопки 'Напонимание об оферте'."""
    try:
        telegram_id = message.from_user.id if message.from_user else message.chat.id
        settings = await OfferSettingsRepository.get_or_create(telegram_id)
        status_text = "включен" if settings.alerts_enabled else "выключен"
        await message.delete()
        text = (
            f"*Напоминание об оферте*\n\n"
            f"Не пропустите важную дату — получайте уведомления о приближающейся оферте (PUT-опцион) заранее.\n\n"
            f"*Как работает:*\n"
            f"• Выберите диапазон — за сколько дней напомнить (например, за 20 и за 7 дней)\n"
            f"• Укажите удобное время уведомления\n"
            f"• Бот напомнит вам точно в срок\n\n"
            f"Статус: *{status_text}*\n\n"
            f"[Что такое оферта](https://www.google.com/search?q=что+такое+оферта+в+облигациях)"
        )

        builder = KeyboardHelper.create_offer_alerts_keyboard(settings.alerts_enabled)
        await message.answer(
            text=text,
            parse_mode="Markdown",
            reply_markup=builder.as_markup(),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
    except Exception as e:
        logger.error(f"Ошибка при обработке кнопки 'Напоминание об оферте': {e}")
        await message.answer("Произошла ошибка при обработке кнопки 'Напоминание об оферте'")


@router.message(F.text == NotificationKeybordButtonTexts.PRICE_ALERT.value)
async def handle_monitoring_button(message: Message) -> None:
    """Обработка кнопки 'Мониторинг'."""
    try:
        telegram_id = message.from_user.id if message.from_user else message.chat.id
        settings = await PriceAlertStorage.get_or_create_user_settings(telegram_id)

        status_text = "включен" if settings.alerts_enabled else "выключен"
        await message.delete()
        message_text = (
            f"<b>Мониторинг цен облигаций</b>\n\n"
            f"Получайте уведомления при значительных изменениях цен "
            f"облигаций в вашем портфеле.\n\n"
            f"Статус: <b>{status_text}</b>"
        )

        if settings.alerts_enabled:
            message_text += (
                f"\n\n<b>Текущие пороги:</b>\n\n"
                f"Падение:\n"
                f"  • Умеренное: {settings.drop_warning_threshold}%\n"
                f"  • Сильное: {settings.drop_critical_threshold}%\n\n"
                f"Рост:\n"
                f"  • Умеренное: {settings.rise_warning_threshold}%\n"
                f"  • Сильное: {settings.rise_critical_threshold}%"
            )

        builder = KeyboardHelper.create_price_alerts_keyboard(settings.alerts_enabled)
        await message.answer(message_text, reply_markup=builder.as_markup(), parse_mode="HTML")

    except Exception as e:
        logger.error(f"Ошибка при обработке кнопки 'Мониторинг': {e}")
        await message.answer("Произошла ошибка")
