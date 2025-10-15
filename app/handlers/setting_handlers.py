"""Обработчик для настроект."""

import logging

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from core.enums import CallbackData
from invest.invest import check_token
from keyboards import KeyboardHelper
from storage import UserStorage

logger = logging.getLogger(__name__)

waiting_for_token: set[int] = set()


class TokenStates(StatesGroup):
    waiting_for_token = State()


class SettingHandler:
    """Обработчик для настроект."""

    @classmethod
    async def handle_settings(cls, callback: CallbackQuery, state: FSMContext) -> None:
        """Обработчик для настроект."""
        try:
            if callback.data == CallbackData.ADD_TOKEN.value:
                if callback.message:
                    await callback.message.answer("Жду токен", parse_mode="HTML")
                    await state.set_state(TokenStates.waiting_for_token)
                await callback.answer()

            elif callback.data == CallbackData.RM_TOKEN.value:
                if callback.message:
                    await callback.message.answer(
                        "Для удаленния напиши 'удалить' без кавычек.", parse_mode="HTML"
                    )
                await callback.answer()

        except Exception as e:
            logger.error(f"Ошибка при обработке запроса: {e}")

            await callback.answer("Произошла ошибка при обработке запроса")

    @staticmethod
    async def handle_token_message(message: Message, state: FSMContext) -> None:
        """Обработчик для токена."""
        telegram_id = message.chat.id
        token = str(message.text).strip()
        if check_token(token):
            await UserStorage.add_token(telegram_id=telegram_id, token=token)
            main_keyboard = KeyboardHelper.create_main_keyboard()
            await message.answer("Токен успешно сохранён!", reply_markup=main_keyboard)
            await state.clear()
        else:
            await message.answer("Некорректный токен! Попробуйте ещё раз")
