"""Основные обработчики бота."""

import logging
from datetime import date

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from core.clients.backend import (
    BackendError,
    MaturityItem,
    OfferItem,
    PositionAccount,
    UserNotFound,
    get_maturities,
    get_offers,
)
from core.enums import MainKeyboardButtonTexts, Messages
from features.analytics import EventName, sanitize_source, track
from features.coupons.keyboards import create_coupons_keyboard
from features.menu import render_hub
from features.onboarding import start_onboarding
from features.users.keyboards import create_settings_keyboard
from features.users.repository import BotUserRepository

from .keyboards import create_main_keyboard, create_new_user_keyboard

logger = logging.getLogger(__name__)

router: Router = Router()


_CURRENCY_SIGNS = {"SUR": "₽", "RUB": "₽", "USD": "$", "EUR": "€"}


def _currency(faceunit: str) -> str:
    return _CURRENCY_SIGNS.get(faceunit.upper(), faceunit.upper())


def _format_date(value: date | None) -> str:
    return value.strftime("%d.%m.%Y") if value else "—"


def _num(value: float) -> str:
    """Целое число с пробелом в качестве разделителя разрядов."""
    return f"{value:,.0f}".replace(",", " ")


def _format_accounts(accounts: list[PositionAccount]) -> str:
    return " ".join(f"\n    {acc.account_name} - {_num(acc.quantity)} шт." for acc in accounts)


def _format_maturities(maturities: list[MaturityItem]) -> str:
    lines = []
    for i, item in enumerate(maturities, 1):
        currency = _currency(item.faceunit)
        days = f" ({item.days_left} дн.)" if item.days_left is not None else ""

        block = [
            f"{i}. <code>{item.secid}</code>",
            f"   {item.name}",
            f"   Погашение: {_format_date(item.maturity_date)}{days}",
        ]

        qty_line = f"   Кол-во: {_num(item.quantity)} шт."
        if item.facevalue is not None:
            qty_line += (
                f" x {_num(item.facevalue)} = {_num(item.quantity * item.facevalue)} {currency}"
            )
        block.append(qty_line)
        if item.accounts:
            block.append(f"   Счета: {_format_accounts(item.accounts)}\n")

        # block.append(f"   MOEX: <a href='{item.moex_link}'>{item.shortname}</a>\n")
        lines.append("\n".join(block))
    return "\n".join(lines)


def _format_offers(offers: list[OfferItem]) -> str:
    lines = []
    for i, item in enumerate(offers, 1):
        currency = _currency(item.faceunit)
        days = f" ({item.days_left} дн.)" if item.days_left is not None else ""

        block = [
            f"{i}. <code>{item.secid}</code>",
            f"   {item.name}",
            f"   {item.offer_type}: {_format_date(item.offer_date)}{days}",
        ]
        if item.date_start or item.date_end:
            block.append(
                f"   Приём заявок: {_format_date(item.date_start)} — {_format_date(item.date_end)}"
            )
        if item.price is not None:
            price_line = f"   Цена выкупа: {item.price:g}%"
            if item.facevalue is not None:
                price_line += f" ({_num(item.facevalue)} {currency})"
            block.append(price_line)

        qty_line = f"   Кол-во: {_num(item.quantity)} шт."
        if item.facevalue is not None:
            qty_line += (
                f" x {_num(item.facevalue)} = {_num(item.quantity * item.facevalue)} {currency}"
            )
        block.append(qty_line)

        block.append(f"   Погашение: {_format_date(item.maturity_date)}")
        if item.accounts:
            block.append(f"   Счета: {_format_accounts(item.accounts)}\n")

        # block.append(f"   MOEX: <a href='{item.moex_link}'>{item.shortname}</a>")
        lines.append("\n".join(block))
    return "\n".join(lines)


@router.message(Command("start"))
async def start_handler(message: Message, command: CommandObject) -> None:
    """Обработчик команды /start.

    Args:
        message: Сообщение с командой.
        command: Разобранная команда. ``command.args`` содержит deep-link
            payload из ``t.me/<bot>?start=<payload>`` — источник привлечения.

    """
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
        await track(
            EventName.BOT_START,
            telegram_id=message.chat.id,
            action="start",
            is_new_user=is_new_user,
            has_token=user_has_token,
            source=sanitize_source(command.args),
        )
        if user_has_token:
            await message.answer(Messages.ALREADY_KNOWN.value, reply_markup=main_keyboard)
        else:
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
    sent = await message.answer("Загружаю данные о погашениях...")
    user_id = message.from_user.id if message.from_user else message.chat.id

    outcome = "ok"
    items = 0
    try:
        maturities = await get_maturities(user_id, limit=5)
        items = len(maturities)
        response = (
            Messages.MATURITIES_TITLE.value + _format_maturities(maturities)
            if maturities
            else Messages.NO_BONDS.value
        )
    except UserNotFound:
        # Бэкенд не знает пользователя — портфель ещё не синхронизирован.
        logger.info(f"Бэкенд не знает пользователя {user_id}")
        response = Messages.NOT_TOKEN.value
        outcome = "no_token"
    except BackendError as e:
        logger.error(f"Ошибка при получении погашений: {e}")
        response = "Не удалось получить данные о погашениях, попробуйте позже."
        outcome = "backend_error"
    except Exception as e:
        logger.error(f"Ошибка при получении погашений: {e}", exc_info=True)
        response = "Произошла ошибка при получении данных о погашениях"
        outcome = "error"

    await track(
        EventName.DATA_SCREEN_VIEWED,
        telegram_id=user_id,
        action="maturities",
        screen="maturities",
        items=items,
        outcome=outcome,
    )
    await sent.delete()
    await message.answer(response, parse_mode="HTML")


@router.message(F.text == MainKeyboardButtonTexts.OFFERS.value)
async def handle_offers_button(message: Message) -> None:
    """Обработка кнопки 'Оферты'."""
    sent = await message.answer("Загружаю данные об офертах...")
    user_id = message.from_user.id if message.from_user else message.chat.id

    outcome = "ok"
    items = 0
    try:
        offers = await get_offers(user_id, limit=5)
        items = len(offers)
        response = (
            Messages.OFFERS_TITLE.value + _format_offers(offers)
            if offers
            else Messages.NO_OFFERS.value
        )
    except UserNotFound:
        # Бэкенд не знает пользователя — портфель ещё не синхронизирован.
        logger.info(f"Бэкенд не знает пользователя {user_id}")
        response = Messages.NOT_TOKEN.value
        outcome = "no_token"
    except BackendError as e:
        logger.error(f"Ошибка при получении оферт: {e}")
        response = "Не удалось получить данные об офертах, попробуйте позже."
        outcome = "backend_error"
    except Exception as e:
        logger.error(f"Ошибка при получении оферт: {e}", exc_info=True)
        response = "Произошла ошибка при получении данных об офертах"
        outcome = "error"

    await track(
        EventName.DATA_SCREEN_VIEWED,
        telegram_id=user_id,
        action="offers",
        screen="offers",
        items=items,
        outcome=outcome,
    )
    await sent.delete()
    await message.answer(response, parse_mode="HTML")


@router.message(F.text == MainKeyboardButtonTexts.PRICE.value)
async def handle_price_button(message: Message) -> None:
    """Обработка кнопки 'Цена'."""
    await message.delete()
    await message.answer(
        text="<b>Цена</b>\n\n"
        "Сейчас бот полностью <b>бесплатный</b>.\n\n"
        "Он находится в стадии разработки, тестирование текущего функционала "
        "и внедрении нового.\n\n"
        "Прими участие в развитие — @bondelo_chat.",
        parse_mode="HTML",
    )
