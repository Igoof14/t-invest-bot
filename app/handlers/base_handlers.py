"""Основные обработчики бота."""

import logging

from aiogram import F
from aiogram.types import Message
from core.enums import Messages
from invest.bonds import get_nearest_maturities, get_nearest_offers
from keyboards import KeyboardHelper
from storage import AlertStorage, BotUserStorage

logger = logging.getLogger(__name__)


async def start_handler(message: Message) -> None:
    """Обработчик команды /start."""
    try:
        main_keyboard = KeyboardHelper.create_main_keyboard()
        new_user_keyboard = KeyboardHelper.create_new_user_keyboard()

        is_new_user = await BotUserStorage.add_user(
            telegram_id=message.chat.id,
            username=message.from_user.username if message.from_user else None,
            first_name=message.from_user.first_name if message.from_user else None,
            last_name=message.from_user.last_name if message.from_user else None,
        )
        user_has_token = await BotUserStorage.has_token(telegram_id=message.chat.id)
        logger.info(
            f"Пользователь {message.chat.id}: новый={is_new_user}, есть_токен={user_has_token}"
        )
        if user_has_token:
            await message.answer(Messages.ALREADY_KNOWN.value, reply_markup=main_keyboard)
        elif is_new_user:
            await message.answer(Messages.WELCOME.value, reply_markup=new_user_keyboard)
        else:
            await message.answer(Messages.NOT_TOKEN.value, reply_markup=new_user_keyboard)

        logger.info(f"Всего пользователей: {await BotUserStorage.get_user_count()}")

    except Exception as e:
        logger.error(f"Ошибка в start handler: {e}")
        await message.answer("Произошла ошибка при запуске")


async def handle_coupons_button(message: Message) -> None:
    """Обработка кнопки 'Купоны'."""
    try:
        builder = KeyboardHelper.create_coupons_inline_keyboard()
        await message.answer(Messages.COUPONS_PROMPT.value, reply_markup=builder.as_markup())
    except Exception as e:
        logger.error(f"Ошибка при обработке кнопки купонов: {e}")
        await message.answer("Произошла ошибка")


async def handle_help_button(message: Message) -> None:
    """Обработка кнопки 'Помощь'."""
    try:
        await message.answer(Messages.HELP_TEXT.value)
    except Exception as e:
        logger.error(f"Ошибка при обработке кнопки помощи: {e}")
        await message.answer("Произошла ошибка при получении справки")


async def handle_my_reports_button(message: Message) -> None:
    """Обработка кнопки 'Мои отчёты'."""
    try:
        await message.answer("Функция 'Мои отчёты' будет доступна в следующих обновлениях")
    except Exception as e:
        logger.error(f"Ошибка при обработке кнопки 'Мои отчёты': {e}")
        await message.answer("Произошла ошибка")


async def handle_settings_button(message: Message) -> None:
    """Обработка кнопки 'Настройки'."""
    try:
        build = KeyboardHelper.create_settings_keyboard()
        await message.answer("Настройки", reply_markup=build.as_markup())
    except Exception as e:
        logger.error(f"Ошибка при обработке кнопки 'Настройки': {e}")
        await message.answer("Произошла ошибка")


async def handle_maturities_button(message: Message) -> None:
    """Обработка кнопки 'Погашения'."""
    try:
        await message.answer("Загружаю данные о погашениях...")
        user_id = message.from_user.id if message.from_user else message.chat.id
        maturities_data = await get_nearest_maturities(user_id)

        if maturities_data:
            response = Messages.MATURITIES_TITLE.value + maturities_data
        else:
            response = Messages.NO_BONDS.value

        await message.answer(response, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка при получении погашений: {e}")
        await message.answer("Произошла ошибка при получении данных о погашениях")


async def handle_offers_button(message: Message) -> None:
    """Обработка кнопки 'Оферты'."""
    try:
        await message.answer("Загружаю данные об офертах...\nЭто может занять некоторое время.")
        user_id = message.from_user.id if message.from_user else message.chat.id
        offers_data = await get_nearest_offers(user_id)

        if offers_data:
            response = Messages.OFFERS_TITLE.value + offers_data
        else:
            response = Messages.NO_OFFERS.value

        await message.answer(response, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка при получении оферт: {e}")
        await message.answer("Произошла ошибка при получении данных об офертах")


async def handle_monitoring_button(message: Message) -> None:
    """Обработка кнопки 'Мониторинг'."""
    try:
        telegram_id = message.from_user.id if message.from_user else message.chat.id
        settings = await AlertStorage.get_or_create_user_settings(telegram_id)

        status_text = "включен" if settings.alerts_enabled else "выключен"
        message_text = (
            f"<b>Мониторинг цен облигаций</b>\n\n"
            f"Получайте уведомления при значительных изменениях цен "
            f"облигаций в вашем портфеле.\n\n"
            f"Статус: <b>{status_text}</b>"
        )

        if settings.alerts_enabled:
            message_text += (
                f"\n\nТекущие пороги:\n"
                f"Падение: warning {settings.drop_warning_threshold}%, "
                f"critical {settings.drop_critical_threshold}%\n"
                f"Рост: warning {settings.rise_warning_threshold}%, "
                f"critical {settings.rise_critical_threshold}%"
            )

        builder = KeyboardHelper.create_price_alerts_keyboard(settings.alerts_enabled)
        await message.answer(message_text, reply_markup=builder.as_markup(), parse_mode="HTML")

    except Exception as e:
        logger.error(f"Ошибка при обработке кнопки 'Мониторинг': {e}")
        await message.answer("Произошла ошибка")
