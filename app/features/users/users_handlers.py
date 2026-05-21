"""Обработчик для настроект."""

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from core.clients.t_invest.common_func import check_token
from core.enums import SettingsCallbackData
from features.users.repository import BotUserRepository

from ..base.main_keyboards import KeyboardHelper

logger = logging.getLogger(__name__)
router = Router()
waiting_for_token: set[int] = set()


class TokenStates(StatesGroup):
    """Режим ожидания токена для добавления или удаления."""

    waiting_for_token = State()
    waiting_for_delete_confirmation = State()


callback_values = {
    SettingsCallbackData.ADD_TOKEN.value,
    SettingsCallbackData.RM_TOKEN.value,
}


@router.callback_query(F.data.in_(callback_values))
async def handle_settings(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработчик для настроект."""
    try:
        if callback.data == SettingsCallbackData.ADD_TOKEN.value:
            if callback.message:
                await callback.message.answer(
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
    if await check_token(token):
        logger.info(f"Токен пользователя {telegram_id} валиден")
        success = await BotUserRepository.add_token(telegram_id=telegram_id, token=token)
        if success:
            main_keyboard = KeyboardHelper.create_main_keyboard()
            await message.answer("Токен успешно сохранён!", reply_markup=main_keyboard)
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
            new_user_keyboard = KeyboardHelper.create_new_user_keyboard()
            await message.answer("Токен успешно удалён!", reply_markup=new_user_keyboard)
        else:
            await message.answer("Ошибка при удалении токена.")
        await state.clear()
    else:
        await message.answer("Удаление отменено.")
        await state.clear()
