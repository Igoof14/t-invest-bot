import logging
import re
from datetime import datetime
from typing import Literal

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from common.utils.bot_utils import pluralize_days

from .keyboards import create_offer_alert_setting_keyboard, create_offer_alerts_keyboard
from .repository import OfferSettingsRepository
from .schemas import OfferAlertCallback

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(OfferAlertCallback.filter(F.action == "toggle"))
async def handle_toggle_alerts(callback: CallbackQuery, callback_data: OfferAlertCallback) -> None:
    """Обработчик включения/выключения уведомлений об офертах."""
    try:
        telegram_id = callback.from_user.id
        new_state = await OfferSettingsRepository.toggle_alerts(telegram_id)
        settings = await OfferSettingsRepository.get_or_create(telegram_id)

        status_text = "включен" if new_state else "выключен"
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
        if new_state:
            text += (
                f"\n\n*Текущие настройки:*\n\n"
                f"Первое напоминаие за: {settings.first_alert} {pluralize_days(settings.first_alert)}\n"
                f"Второе напоминаие за: {settings.second_alert} {pluralize_days(settings.second_alert)}\n"
                f"Время уведомления: {str(settings.notification_time)[:-3]} МСК"  # Удаляем секунды
            )
        builder = create_offer_alerts_keyboard(new_state)

        if callback.message and isinstance(callback.message, Message):
            await callback.message.edit_text(
                text,
                reply_markup=builder.as_markup(),
                parse_mode="Markdown",
            )

        await callback.answer("Уведомления " + ("включены" if new_state else "выключены"))

    except Exception as e:
        logger.error(f"Ошибка при переключении уведомлений об офертах: {e}")
        await callback.answer("Произошла ошибка")


@router.callback_query(OfferAlertCallback.filter(F.action == "setting"))
async def handle_offer_alert_setting(callback: CallbackQuery) -> None:
    """Обработчик для кнопки настроек уведомлений об офертах."""
    try:
        telegram_id = callback.from_user.id
        settings = await OfferSettingsRepository.get_or_create(telegram_id)
        status_text: Literal["включен", "выключен"] = (
            "включен" if settings.alerts_enabled else "выключен"
        )
        message_text = f"<b>Настройки уведомлений об офертах</b>\n\n"

        if settings.alerts_enabled:
            message_text += (
                f"<b>Текущие настройки:</b>\n\n"
                f"Первое напоминаие за: {settings.first_alert} {pluralize_days(settings.first_alert)}\n"
                f"Второе напоминаие за: {settings.second_alert} {pluralize_days(settings.second_alert)}\n"
                f"Время уведомления: {str(settings.notification_time)[:-3]} МСК\n\n"
                f"Выбери что настроить: "
            )

        builder = create_offer_alert_setting_keyboard()

        if callback.message and isinstance(callback.message, Message):
            await callback.message.edit_text(
                message_text,
                reply_markup=builder.as_markup(),
                parse_mode="HTML",
            )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при показе меню уведомлений: {e}")
        await callback.answer("Произошла ошибка")


class OfferAlertStates(StatesGroup):
    """Состояния для управления уведомлениями об офертах."""

    waiting_for_first = State()
    waiting_for_second = State()
    waiting_for_time = State()


@router.callback_query(
    OfferAlertCallback.filter(F.action.in_(["set_first", "set_second", "set_time"]))
)
async def handle_set_settings(
    callback: CallbackQuery, callback_data: OfferAlertCallback, state
) -> None:
    """Обработчик настроек."""
    try:
        if callback.message is None:
            raise ValueError("callback.message is None")

        if callback_data.action == "set_first":
            await callback.message.answer(
                "Введите количество дней за которое нужно напомнить об оферте (число не больше 50):"
            )
            await state.set_state(OfferAlertStates.waiting_for_first)

        elif callback_data.action == "set_second":
            await callback.message.answer(
                "Введите значение для второго напоминания (число не больше первого):"
            )
            await state.set_state(OfferAlertStates.waiting_for_second)

        elif callback_data.action == "set_time":
            await callback.message.answer(
                "Введите время напоминания в формате HH:MM (например, 15:30):"
            )
            await state.set_state(OfferAlertStates.waiting_for_time)

            await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при установке первого напоминания: {e}")
        await callback.answer("Произошла ошибка")


@router.message(OfferAlertStates.waiting_for_first)
async def process_first_alert(message: Message, state: FSMContext):
    """Обработчик для установки первого напоминания."""
    text = message.text.strip() if message.text else ""
    if not text.isdigit():
        await message.answer("Пожалуйста, введите целое число.")
        return

    val = int(text)
    if val > 50 or val <= 0:
        await message.answer("Число должно быть > 0 и <= 50. Попробуйте еще раз:")
        return

    try:
        telegram_id = message.chat.id
        await message.delete()
        await OfferSettingsRepository.update(telegram_id, first_alert=val)
        await message.answer(f"Первое напоминание успешно установлено: {val}")
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при сохранении: {e}")
        await message.answer("Произошла ошибка при сохранении")


@router.message(OfferAlertStates.waiting_for_second)
async def process_second_alert(message: Message, state: FSMContext):
    """Обработчик для установки второго напоминания."""
    text = message.text.strip() if message.text else ""
    telegram_id = message.chat.id
    if not text.isdigit():
        await message.answer("Пожалуйста, введите целое число.")
        return

    val = int(text)

    if val > 50 or val <= 0:
        await message.answer("Число должно быть > 0 и <= 50. Попробуйте еще раз:")
        return

    try:
        telegram_id = message.chat.id
        await message.delete()
        await OfferSettingsRepository.update(telegram_id, second_alert=val)
        await message.answer(f"Второе напоминание успешно установлено: {val}")
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при сохранении: {e}")
        await message.answer("Произошла ошибка при сохранении")


@router.message(OfferAlertStates.waiting_for_time)
async def process_time_alert(message: Message, state: FSMContext):
    """Обработчик для установки времени напоминания."""
    text = message.text.strip() if message.text else ""

    time_pattern = r"^([01][0-9]|2[0-3]):[0-5][0-9]$"

    if not re.match(time_pattern, text):
        await message.answer(
            "Неверный формат времени! Введите в формате ЧЧ:ММ (например, 09:00 или 18:30):"
        )
        return

    try:
        telegram_id = message.chat.id
        notification_time = datetime.strptime(text, "%H:%M").time()
        await message.delete()
        await OfferSettingsRepository.update(telegram_id, notification_time=notification_time)
        await message.answer(f"Время напоминания успешно установлено: {text} мск")
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при сохранении: {e}")
        await message.answer("Произошла ошибка при сохранении")
