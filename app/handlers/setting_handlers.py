"""Обработчик для настроект."""

import logging

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from core.enums import CallbackData, Messages
from invest.invest import check_token
from keyboards import KeyboardHelper
from storage import AlertStorage, BotUserStorage

logger = logging.getLogger(__name__)

waiting_for_token: set[int] = set()


class TokenStates(StatesGroup):
    waiting_for_token = State()
    waiting_for_delete_confirmation = State()


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
                        "Для удаления напиши 'удалить' без кавычек.", parse_mode="HTML"
                    )
                    await state.set_state(TokenStates.waiting_for_delete_confirmation)
                await callback.answer()

        except Exception as e:
            logger.error(f"Ошибка при обработке запроса: {e}")

            await callback.answer("Произошла ошибка при обработке запроса")

    @staticmethod
    async def handle_token_message(message: Message, state: FSMContext) -> None:
        """Обработчик для токена."""
        telegram_id = message.chat.id
        token = str(message.text).strip()
        logger.info(f"Получен токен от пользователя {telegram_id}")
        if await check_token(token):
            logger.info(f"Токен пользователя {telegram_id} валиден")
            success = await BotUserStorage.add_token(telegram_id=telegram_id, token=token)
            if success:
                main_keyboard = KeyboardHelper.create_main_keyboard()
                await message.answer("Токен успешно сохранён!", reply_markup=main_keyboard)
                await state.clear()
            else:
                logger.warning(f"Не удалось сохранить токен для {telegram_id}")
                await message.answer(
                    "Ошибка сохранения токена. Попробуйте /start и повторите попытку."
                )
                await state.clear()
        else:
            logger.warning(f"Токен пользователя {telegram_id} невалиден")
            await message.answer("Некорректный токен! Попробуйте ещё раз")

    @staticmethod
    async def handle_delete_confirmation(message: Message, state: FSMContext) -> None:
        """Обработчик подтверждения удаления токена."""
        telegram_id = message.chat.id
        text = str(message.text).strip().lower()
        if text == "удалить":
            success = await BotUserStorage.remove_token(telegram_id=telegram_id)
            if success:
                new_user_keyboard = KeyboardHelper.create_new_user_keyboard()
                await message.answer("Токен успешно удалён!", reply_markup=new_user_keyboard)
            else:
                await message.answer("Ошибка при удалении токена.")
            await state.clear()
        else:
            await message.answer("Удаление отменено.")
            await state.clear()


class ThresholdStates(StatesGroup):
    """Состояния для настройки порогов."""

    waiting_for_drop_warning = State()
    waiting_for_drop_critical = State()
    waiting_for_rise_warning = State()
    waiting_for_rise_critical = State()


class AlertSettingsHandler:
    """Обработчик для настроек уведомлений о ценах."""

    @classmethod
    async def handle_price_alerts_menu(cls, callback: CallbackQuery) -> None:
        """Показывает меню настроек уведомлений о ценах."""
        try:
            telegram_id = callback.from_user.id
            settings = await AlertStorage.get_or_create_user_settings(telegram_id)

            # Формируем текст с текущим состоянием
            status_text = "включены" if settings.alerts_enabled else "выключены"
            message_text = (
                f"{Messages.PRICE_ALERTS_MENU.value}\n\n"
                f"Статус: <b>{status_text}</b>"
            )

            if settings.alerts_enabled:
                message_text += (
                    f"\n\nТекущие пороги:\n"
                    f"📉 Падение: warning {settings.drop_warning_threshold}%, "
                    f"critical {settings.drop_critical_threshold}%\n"
                    f"📈 Рост: warning {settings.rise_warning_threshold}%, "
                    f"critical {settings.rise_critical_threshold}%"
                )

            builder = KeyboardHelper.create_price_alerts_keyboard(settings.alerts_enabled)

            if callback.message:
                await callback.message.edit_text(
                    message_text,
                    reply_markup=builder.as_markup(),
                    parse_mode="HTML",
                )
            await callback.answer()

        except Exception as e:
            logger.error(f"Ошибка при показе меню уведомлений: {e}")
            await callback.answer("Произошла ошибка")

    @classmethod
    async def handle_toggle_alerts(cls, callback: CallbackQuery) -> None:
        """Переключает состояние уведомлений."""
        try:
            telegram_id = callback.from_user.id
            new_state = await AlertStorage.toggle_alerts(telegram_id)

            if new_state:
                message_text = Messages.PRICE_ALERTS_ENABLED.value
            else:
                message_text = Messages.PRICE_ALERTS_DISABLED.value

            builder = KeyboardHelper.create_price_alerts_keyboard(new_state)

            if callback.message:
                await callback.message.edit_text(
                    message_text,
                    reply_markup=builder.as_markup(),
                    parse_mode="HTML",
                )

            await callback.answer("Уведомления " + ("включены" if new_state else "выключены"))

        except Exception as e:
            logger.error(f"Ошибка при переключении уведомлений: {e}")
            await callback.answer("Произошла ошибка")

    @classmethod
    async def handle_thresholds_menu(cls, callback: CallbackQuery) -> None:
        """Показывает меню настройки порогов."""
        try:
            telegram_id = callback.from_user.id
            settings = await AlertStorage.get_user_settings(telegram_id)

            if not settings:
                await callback.answer("Сначала включите уведомления")
                return

            message_text = (
                f"{Messages.PRICE_ALERTS_SETTINGS_TITLE.value}"
                f"📉 Падение warning: <b>{settings.drop_warning_threshold}%</b>\n"
                f"📉 Падение critical: <b>{settings.drop_critical_threshold}%</b>\n"
                f"📈 Рост warning: <b>{settings.rise_warning_threshold}%</b>\n"
                f"📈 Рост critical: <b>{settings.rise_critical_threshold}%</b>\n\n"
                f"Нажмите на кнопку, чтобы изменить порог."
            )

            builder = KeyboardHelper.create_thresholds_keyboard()

            if callback.message:
                await callback.message.edit_text(
                    message_text,
                    reply_markup=builder.as_markup(),
                    parse_mode="HTML",
                )
            await callback.answer()

        except Exception as e:
            logger.error(f"Ошибка при показе меню порогов: {e}")
            await callback.answer("Произошла ошибка")

    @classmethod
    async def handle_threshold_select(cls, callback: CallbackQuery, state: FSMContext) -> None:
        """Обрабатывает выбор порога для изменения."""
        try:
            threshold_type = callback.data

            prompts = {
                CallbackData.PRICE_ALERTS_DROP_WARNING.value: (
                    "Введите новый порог падения для предупреждения (в %).\n"
                    "Например: 2"
                ),
                CallbackData.PRICE_ALERTS_DROP_CRITICAL.value: (
                    "Введите новый порог падения для критического уведомления (в %).\n"
                    "Например: 5"
                ),
                CallbackData.PRICE_ALERTS_RISE_WARNING.value: (
                    "Введите новый порог роста для предупреждения (в %).\n"
                    "Например: 3"
                ),
                CallbackData.PRICE_ALERTS_RISE_CRITICAL.value: (
                    "Введите новый порог роста для критического уведомления (в %).\n"
                    "Например: 7"
                ),
            }

            states = {
                CallbackData.PRICE_ALERTS_DROP_WARNING.value: ThresholdStates.waiting_for_drop_warning,
                CallbackData.PRICE_ALERTS_DROP_CRITICAL.value: ThresholdStates.waiting_for_drop_critical,
                CallbackData.PRICE_ALERTS_RISE_WARNING.value: ThresholdStates.waiting_for_rise_warning,
                CallbackData.PRICE_ALERTS_RISE_CRITICAL.value: ThresholdStates.waiting_for_rise_critical,
            }

            prompt = prompts.get(threshold_type)
            new_state = states.get(threshold_type)

            if prompt and new_state:
                if callback.message:
                    await callback.message.answer(prompt)
                await state.set_state(new_state)
                await callback.answer()
            else:
                await callback.answer("Неизвестный тип порога")

        except Exception as e:
            logger.error(f"Ошибка при выборе порога: {e}")
            await callback.answer("Произошла ошибка")

    @classmethod
    async def handle_threshold_input(cls, message: Message, state: FSMContext) -> None:
        """Обрабатывает ввод нового значения порога."""
        try:
            telegram_id = message.chat.id
            text = str(message.text).strip().replace(",", ".").replace("%", "")

            try:
                value = float(text)
                if value <= 0 or value > 100:
                    await message.answer(
                        "Значение должно быть больше 0 и не больше 100. Попробуйте ещё раз."
                    )
                    return
            except ValueError:
                await message.answer("Введите число. Например: 2.5")
                return

            current_state = await state.get_state()

            field_map = {
                ThresholdStates.waiting_for_drop_warning.state: "drop_warning_threshold",
                ThresholdStates.waiting_for_drop_critical.state: "drop_critical_threshold",
                ThresholdStates.waiting_for_rise_warning.state: "rise_warning_threshold",
                ThresholdStates.waiting_for_rise_critical.state: "rise_critical_threshold",
            }

            field = field_map.get(current_state)
            if field:
                await AlertStorage.update_user_settings(telegram_id, **{field: value})
                await message.answer(f"Порог успешно изменён на {value}%")
                await state.clear()
            else:
                await message.answer("Неизвестное состояние")
                await state.clear()

        except Exception as e:
            logger.error(f"Ошибка при вводе порога: {e}")
            await message.answer("Произошла ошибка при сохранении")
            await state.clear()
