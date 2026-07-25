"""Основные обработчики бота."""

import logging
from datetime import UTC, datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message
from core.clients.t_invest.bonds import (
    MaturityInfo,
    OfferInfo,
    get_nearest_maturities,
    get_nearest_offers,
)
from core.enums import MainKeyboardButtonTexts, Messages
from features.coupons.keyboards import create_coupons_keyboard
from features.menu import render_hub
from features.onboarding import start_onboarding
from features.users.keyboards import create_settings_keyboard
from features.users.repository import BotUserRepository

from .keyboards import create_main_keyboard, create_new_user_keyboard

logger = logging.getLogger(__name__)

router: Router = Router()


def _format_maturities(maturities: list[MaturityInfo]) -> str:
    now = datetime.now(UTC)
    lines = []
    for i, bond in enumerate(maturities, 1):
        days_left = (bond.maturity_date.date() - now.date()).days
        total_nominal = bond.nominal * bond.quantity
        lines.append(
            f"{i}. <code>{bond.ticker}</code>\n"
            f"   {bond.name}\n"
            f"   Погашение: {bond.maturity_date.strftime('%d.%m.%Y')} ({days_left} дн.)\n"
            f"   Кол-во: {bond.quantity} шт. x {bond.nominal:.0f} = "
            f"{total_nominal:,.0f} {bond.currency.upper()}\n"
            f"   Счёт: {bond.account_name}\n"
        )
    return "\n".join(lines)


def _format_offers(offers: list[OfferInfo]) -> str:
    now = datetime.now(UTC)
    lines = []
    for i, offer in enumerate(offers, 1):
        days_left = (offer.offer_date.date() - now.date()).days
        total_nominal = offer.nominal * offer.quantity
        lines.append(
            f"{i}. <code>{offer.ticker}</code>\n"
            f"   {offer.name}\n"
            f"   Оферта: {offer.offer_date.strftime('%d.%m.%Y')} ({days_left} дн.)\n"
            f"   Кол-во: {offer.quantity} шт. x {offer.nominal:.0f} = "
            f"{total_nominal:,.0f} {offer.currency.upper()}\n"
            f"   Средняя цена покупки: {offer.average_position_price:,.0f} {offer.currency.upper()}\n"
            f"   MOEX: <a href='{offer.moex_link}'>{offer.ticker}</a>\n"
        )
    return "\n".join(lines)


@router.message(Command("start"))
async def start_handler(message: Message) -> None:
    """Обработчик команды /start."""
    try:
        main_keyboard = create_main_keyboard()
        new_user_keyboard = create_new_user_keyboard()

        is_new_user = await BotUserRepository.add_user(
            telegram_id=message.chat.id,
            username=message.from_user.username if message.from_user else None,
            first_name=message.from_user.first_name if message.from_user else None,
            last_name=message.from_user.last_name if message.from_user else None,
        )
        user_has_token = await BotUserRepository.has_token(telegram_id=message.chat.id)
        logger.info(
            f"Пользователь {message.chat.id}: новый={is_new_user}, есть_токен={user_has_token}"
        )
        if user_has_token:
            await message.answer(Messages.ALREADY_KNOWN.value, reply_markup=main_keyboard)
        else:
            # Пользователь без токена (новый или вернувшийся) — ведём по воронке.
            # Короткое сообщение закрепляет reply-клавиатуру (Настройки/Помощь),
            # которой не может быть у инлайн-экранов воронки.
            await message.answer("Добро пожаловать 👋", reply_markup=new_user_keyboard)
            await start_onboarding(message)

        logger.info(f"Всего пользователей: {await BotUserRepository.get_user_count()}")

    except Exception as e:
        logger.error(f"Ошибка в start handler: {e}")
        await message.answer("Произошла ошибка при запуске")


@router.message(F.text == MainKeyboardButtonTexts.NOTIFICATIONS.value)
async def handle_notifications_button(message: Message) -> None:
    """Открывает инлайн-хаб «Уведомления»."""
    telegram_id = message.from_user.id if message.from_user else message.chat.id
    text, markup = await render_hub(telegram_id)
    await message.answer(text, reply_markup=markup, parse_mode="HTML")
    await message.delete()


@router.message(F.text == MainKeyboardButtonTexts.COUPONS.value)
async def handle_coupons_button(message: Message) -> None:
    """Обработка кнопки 'Купоны'."""
    try:
        builder = create_coupons_keyboard()
        await message.answer(Messages.COUPONS_PROMPT.value, reply_markup=builder.as_markup())
    except Exception as e:
        logger.error(f"Ошибка при обработке кнопки купонов: {e}")
        await message.answer("Произошла ошибка")


@router.message(F.text == MainKeyboardButtonTexts.HELP.value)
async def handle_help_button(message: Message) -> None:
    """Обработка кнопки 'Помощь'."""
    try:
        await message.delete()
        await message.answer(Messages.HELP_TEXT.value)
    except Exception as e:
        logger.error(f"Ошибка при обработке кнопки помощи: {e}")
        await message.answer("Произошла ошибка при получении справки")


@router.message(F.text == MainKeyboardButtonTexts.SETTINGS.value)
async def handle_settings_button(message: Message) -> None:
    """Обработка кнопки 'Настройки'."""
    try:
        build = create_settings_keyboard()
        await message.delete()
        await message.answer("Настройки", reply_markup=build.as_markup())
    except Exception as e:
        logger.error(f"Ошибка при обработке кнопки 'Настройки': {e}")
        await message.answer("Произошла ошибка")


@router.message(F.text == MainKeyboardButtonTexts.MATURITIES.value)
async def handle_maturities_button(message: Message) -> None:
    """Обработка кнопки 'Погашения'."""
    try:
        await message.answer("Загружаю данные о погашениях...")
        user_id = message.from_user.id if message.from_user else message.chat.id
        maturities = await get_nearest_maturities(user_id)

        if maturities is None:
            response = Messages.NOT_TOKEN.value
        elif maturities:
            response = Messages.MATURITIES_TITLE.value + _format_maturities(maturities)
        else:
            response = Messages.NO_BONDS.value

        await message.answer(response, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка при получении погашений: {e}")
        await message.answer("Произошла ошибка при получении данных о погашениях")


@router.message(F.text == MainKeyboardButtonTexts.OFFERS.value)
async def handle_offers_button(message: Message) -> None:
    """Обработка кнопки 'Оферты'."""
    try:
        sent = await message.answer("Загружаю данные об офертах...")
        user_id = message.from_user.id if message.from_user else message.chat.id
        offers = await get_nearest_offers(user_id)

        if offers is None:
            response = Messages.NOT_TOKEN.value
        elif offers:
            response = Messages.OFFERS_TITLE.value + _format_offers(offers)
        else:
            response = Messages.NO_OFFERS.value
        await sent.delete()
        await message.answer(response, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка при получении оферт: {e}")
        await message.answer("Произошла ошибка при получении данных об офертах")


@router.message(F.text == MainKeyboardButtonTexts.PRICE.value)
async def handle_price_button(message: Message) -> None:
    """Обработка кнопки 'Цена'."""
    await message.delete()
    await message.answer(
        text="*Цена*\n\n"
        "Сейчас бот полностью *бесплатный*.\n\n"
        "Он находится в стадии разработки, тектирование текущего функционала "
        "и внедрении нового.\n\n"
        "Прими участие в развитие - @bondelo_chat.",
        parse_mode="Markdown",
    )
