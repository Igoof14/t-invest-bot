"""Обработчик для настроект."""

import asyncio
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from common.utils.bot_utils import pluralize_bonds
from core.clients.bonds_sync.client import sync_user_bonds
from core.clients.t_invest.common_func import check_token
from features.analytics import EventName, track
from features.base.keyboards import create_main_keyboard, create_new_user_keyboard
from features.users.repository import BotUserRepository

from .enums import SettingsCallbackData

logger = logging.getLogger(__name__)
router = Router()
waiting_for_token: set[int] = set()

# Удержание фоновых задач синхронизации облигаций от сборки GC до завершения.
_SYNC_TASKS: set[asyncio.Task[None]] = set()


async def _sync_bonds_and_notify(message: Message, telegram_id: int) -> None:
    """Синхронизирует облигации и сообщает пользователю результат.

    Args:
        message: Сообщение с токеном — в его чат уходит уведомление.
        telegram_id: Telegram ID пользователя, для которого запускается синк.

    """
    bonds_synced = await sync_user_bonds(telegram_id)

    if bonds_synced is None:
        text = (
            "Не удалось синхронизировать список облигаций. "
            "Мы попробуем ещё раз — данные появятся чуть позже."
        )
    elif bonds_synced:
        text = (
            f"Список облигаций синхронизирован: "
            f"{bonds_synced} {pluralize_bonds(bonds_synced)} в портфеле."
        )
    else:
        text = "Список облигаций синхронизирован — облигаций в портфеле не нашлось."

    await track(
        EventName.BONDS_SYNCED,
        telegram_id=telegram_id,
        count=bonds_synced,
        ok=bonds_synced is not None,
    )

    try:
        await message.answer(text)
    except TelegramAPIError:
        logger.error(
            f"Не удалось отправить уведомление о синхронизации пользователю {telegram_id}",
            exc_info=True,
        )


def _schedule_bonds_sync(message: Message, telegram_id: int) -> None:
    """Запускает синхронизацию облигаций пользователя в фоне, не блокируя ответ.

    Args:
        message: Сообщение с токеном — в его чат уходит уведомление о результате.
        telegram_id: Telegram ID пользователя, для которого запускается синк.

    """
    task = asyncio.create_task(_sync_bonds_and_notify(message, telegram_id))
    _SYNC_TASKS.add(task)
    task.add_done_callback(_SYNC_TASKS.discard)


class TokenStates(StatesGroup):
    """Режим ожидания токена для добавления или удаления."""

    waiting_for_token = State()
    waiting_for_delete_confirmation = State()


callback_values = {
    SettingsCallbackData.ADD_TOKEN.value,
    SettingsCallbackData.RM_TOKEN.value,
}


async def prompt_for_token(message: Message, state: FSMContext, *, entry: str = "settings") -> None:
    """Показывает экран ввода токена и переводит FSM в ожидание токена.

    Общий шаг для кнопки «Добавить токен» в настройках и финального CTA
    онбординг-воронки.

    Args:
        message: Сообщение, в чат которого отправить инструкцию.
        state: FSM-контекст пользователя.
        entry: Откуда пришёл пользователь — ``onboarding`` или ``settings``.
            Нужен, чтобы считать конверсию двух входов раздельно.

    """
    await message.answer(
        "*Токен доступа*\n\n"
        "Отправьте ваш *Read-only* токен сообщением.\n\n"
        "*Read-only* — токен с правом только на чтение данных. "
        "Он не даёт возможности совершать сделки или переводить средства, "
        "поэтому безопасен для использования в боте.\n\n"
        "[Как получить токен](https://developer.tbank.ru/invest/intro/intro/token)",
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )
    await state.set_state(TokenStates.waiting_for_token)
    await track(EventName.TOKEN_PROMPT_SHOWN, telegram_id=message.chat.id, entry=entry)


@router.callback_query(F.data.in_(callback_values))
async def handle_settings(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработчик для настроект."""
    try:
        if callback.data == SettingsCallbackData.ADD_TOKEN.value:
            if isinstance(callback.message, Message):
                await prompt_for_token(callback.message, state)
            await callback.answer()

        elif callback.data == SettingsCallbackData.RM_TOKEN.value:
            if callback.message:
                await callback.message.answer(
                    "Для удаления напиши 'удалить' без кавычек.", parse_mode="HTML"
                )
                await state.set_state(TokenStates.waiting_for_delete_confirmation)
            await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при обработке запроса: {e}")

        await callback.answer("Произошла ошибка при обработке запроса")


@router.message(TokenStates.waiting_for_token)
async def handle_token_message(message: Message, state: FSMContext) -> None:
    """Обработчик для токена."""
    telegram_id = message.chat.id
    if not message.text:
        await message.answer("Отправьте токен текстовым сообщением")
        return
    token = message.text.strip()
    logger.info(f"Получен токен от пользователя {telegram_id}")
    is_valid = await check_token(token)
    await track(EventName.TOKEN_SUBMITTED, telegram_id=telegram_id, valid=is_valid)
    if is_valid:
        logger.info(f"Токен пользователя {telegram_id} валиден")
        success = await BotUserRepository.add_token(telegram_id=telegram_id, token=token)
        if success:
            await track(EventName.TOKEN_CONNECTED, telegram_id=telegram_id)
            main_keyboard = create_main_keyboard()
            await message.answer(
                "Токен успешно сохранён! Синхронизирую список облигаций...",
                reply_markup=main_keyboard,
            )
            _schedule_bonds_sync(message, telegram_id)
            await state.clear()
        else:
            logger.warning(f"Не удалось сохранить токен для {telegram_id}")
            await message.answer("Ошибка сохранения токена. Попробуйте /start и повторите попытку.")
            await state.clear()
    else:
        logger.warning(f"Токен пользователя {telegram_id} невалиден")
        await message.answer("Некорректный токен! Попробуйте ещё раз")


@router.message(TokenStates.waiting_for_delete_confirmation)
async def handle_delete_confirmation(message: Message, state: FSMContext) -> None:
    """Обработчик подтверждения удаления токена."""
    telegram_id = message.chat.id
    if not message.text:
        await message.answer("Удаление отменено.")
        await state.clear()
        return
    text = message.text.strip().lower()
    if text == "удалить":
        success = await BotUserRepository.remove_token(telegram_id=telegram_id)
        if success:
            await track(EventName.TOKEN_REMOVED, telegram_id=telegram_id)
            new_user_keyboard = create_new_user_keyboard()
            await message.answer("Токен успешно удалён!", reply_markup=new_user_keyboard)
        else:
            await message.answer("Ошибка при удалении токена.")
        await state.clear()
    else:
        await message.answer("Удаление отменено.")
        await state.clear()
