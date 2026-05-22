import logging

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from core.enums import Messages
from .enums import PriceAlertCallbackData

from .keyboards import create_price_alerts_keyboard, create_thresholds_keyboard
from .repository import AlertSettingsRepository

logger = logging.getLogger(__name__)
router: Router = Router()


class ThresholdStates(StatesGroup):
    """Состояния для настройки порогов."""

    waiting_for_drop_warning = State()
    waiting_for_drop_critical = State()
    waiting_for_rise_warning = State()
    waiting_for_rise_critical = State()


@router.callback_query(F.data == PriceAlertCallbackData.PRICE_ALERTS_SETTINGS.value)
async def handle_price_alerts_menu(callback: CallbackQuery) -> None:
    """Обработчик для кнопки 'Настроить пороги'."""
    try:
        telegram_id = callback.from_user.id
        settings = await AlertSettingsRepository.get_or_create(telegram_id)

        # Формируем текст с текущим состоянием
        status_text = "включены" if settings.alerts_enabled else "выключены"
        message_text = f"{Messages.PRICE_ALERTS_MENU.value}\n\nСтатус: <b>{status_text}</b>"

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

        builder = create_price_alerts_keyboard(settings.alerts_enabled)

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


@router.callback_query(F.data == PriceAlertCallbackData.PRICE_ALERTS_TOGGLE.value)
async def handle_toggle_alerts(callback: CallbackQuery) -> None:
    """Обработчик включения/выключения мониторинга цен."""
    try:
        telegram_id = callback.from_user.id
        new_state = await AlertSettingsRepository.toggle_alerts(telegram_id)
        settings = await AlertSettingsRepository.get_or_create(telegram_id)

        status_text = "включен" if new_state else "выключен"
        message_text = (
            f"<b>Мониторинг цен облигаций</b>\n\n"
            f"Получайте уведомления при значительных изменениях цен "
            f"облигаций в вашем портфеле.\n\n"
            f"Статус: <b>{status_text}</b>"
        )
        if new_state:
            message_text += (
                f"\n\n<b>Текущие пороги:</b>\n\n"
                f"Падение:\n"
                f"  • Умеренное: {settings.drop_warning_threshold}%\n"
                f"  • Сильное: {settings.drop_critical_threshold}%\n\n"
                f"Рост:\n"
                f"  • Умеренное: {settings.rise_warning_threshold}%\n"
                f"  • Сильное: {settings.rise_critical_threshold}%"
            )

        builder = create_price_alerts_keyboard(new_state)

        if callback.message and isinstance(callback.message, Message):
            await callback.message.edit_text(
                message_text,
                reply_markup=builder.as_markup(),
                parse_mode="HTML",
            )

        await callback.answer("Уведомления " + ("включены" if new_state else "выключены"))

    except Exception as e:
        logger.error(f"Ошибка при переключении уведомлений: {e}")
        await callback.answer("Произошла ошибка")


@router.callback_query(F.data == PriceAlertCallbackData.PRICE_ALERTS_SETTINGS.value + "_thresholds")
async def handle_thresholds_menu(callback: CallbackQuery) -> None:
    """Показывает меню настройки порогов."""
    try:
        telegram_id = callback.from_user.id
        settings = await AlertSettingsRepository.get(telegram_id)

        if not settings:
            await callback.answer("Сначала включите уведомления")
            return

        message_text = (
            f"<b>Настройка порогов уведомлений</b>\n\n"
            f"<b>Текущие пороги:</b>\n\n"
            f"Падение:\n"
            f"  • Умеренное: <b>{settings.drop_warning_threshold}%</b>\n"
            f"  • Сильное: <b>{settings.drop_critical_threshold}%</b>\n\n"
            f"Рост:\n"
            f"  • Умеренное: <b>{settings.rise_warning_threshold}%</b>\n"
            f"  • Сильное: <b>{settings.rise_critical_threshold}%</b>\n\n"
            f"Нажмите на кнопку, чтобы изменить порог."
        )

        builder = create_thresholds_keyboard()

        if callback.message and isinstance(callback.message, Message):
            await callback.message.edit_text(
                message_text,
                reply_markup=builder.as_markup(),
                parse_mode="HTML",
            )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при показе меню порогов: {e}")
        await callback.answer("Произошла ошибка")


threshold_callbacks = {
    PriceAlertCallbackData.PRICE_ALERTS_DROP_WARNING.value,
    PriceAlertCallbackData.PRICE_ALERTS_DROP_CRITICAL.value,
    PriceAlertCallbackData.PRICE_ALERTS_RISE_WARNING.value,
    PriceAlertCallbackData.PRICE_ALERTS_RISE_CRITICAL.value,
}


@router.callback_query(F.data.in_(threshold_callbacks))
async def handle_threshold_select(callback: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает выбор порога для изменения."""
    try:
        threshold_type = callback.data

        prompts = {
            PriceAlertCallbackData.PRICE_ALERTS_DROP_WARNING.value: (
                "Введите порог умеренного падения (в %).\nНапример: 2"
            ),
            PriceAlertCallbackData.PRICE_ALERTS_DROP_CRITICAL.value: (
                "Введите порог сильного падения (в %).\nНапример: 5"
            ),
            PriceAlertCallbackData.PRICE_ALERTS_RISE_WARNING.value: (
                "Введите порог умеренного роста (в %).\nНапример: 3"
            ),
            PriceAlertCallbackData.PRICE_ALERTS_RISE_CRITICAL.value: (
                "Введите порог сильного роста (в %).\nНапример: 7"
            ),
        }

        states = {
            PriceAlertCallbackData.PRICE_ALERTS_DROP_WARNING.value: ThresholdStates.waiting_for_drop_warning,
            PriceAlertCallbackData.PRICE_ALERTS_DROP_CRITICAL.value: ThresholdStates.waiting_for_drop_critical,
            PriceAlertCallbackData.PRICE_ALERTS_RISE_WARNING.value: ThresholdStates.waiting_for_rise_warning,
            PriceAlertCallbackData.PRICE_ALERTS_RISE_CRITICAL.value: ThresholdStates.waiting_for_rise_critical,
        }

        if threshold_type is not None:
            prompt = prompts.get(threshold_type)
            new_state = states.get(threshold_type)

        if prompt and new_state:
            if callback.message:
                sent_message: Message = await callback.message.answer(prompt)
                await state.update_data(prompt_message_id=sent_message.message_id)

            await state.set_state(new_state)
            await callback.answer()
        else:
            await callback.answer("Неизвестный тип порога")

    except Exception as e:
        logger.error(f"Ошибка при выборе порога: {e}")
        await callback.answer("Произошла ошибка")


@router.message(
    StateFilter(
        ThresholdStates.waiting_for_drop_warning,
        ThresholdStates.waiting_for_drop_critical,
        ThresholdStates.waiting_for_rise_warning,
        ThresholdStates.waiting_for_rise_critical,
    )
)
async def handle_threshold_input(message: Message, state: FSMContext) -> None:
    """Обрабатывает ввод нового значения порога."""
    try:
        telegram_id = message.chat.id
        if not message.text:
            await message.answer("Введите число. Например: 2.5")
            return
        text = message.text.strip().replace(",", ".").replace("%", "")

        try:
            value = float(text)
            if value <= 0 or value > 100:
                await message.answer(
                    "Значение должно быть больше 0 и меньше 100. Попробуйте ещё раз."
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
            await AlertSettingsRepository.update(telegram_id, **{field: value})

            state_data = await state.get_data()
            prompt_message_id = state_data.get("prompt_message_id")

            if prompt_message_id:
                from aiogram.exceptions import TelegramBadRequest

                try:
                    if isinstance(message.bot, Bot):
                        await message.bot.delete_message(
                            chat_id=message.chat.id, message_id=prompt_message_id
                        )
                    else:
                        logger.warning("bot is not an instance of Bot, skipping delete_message")
                except TelegramBadRequest as e:
                    logger.error(f"Неожиданная ошибка при удалении: {e}")

            await message.delete()

            await message.answer(f"Порог успешно изменён на {value}%")
            await state.clear()
        else:
            await message.answer("Неизвестное состояние")
            await state.clear()

    except Exception as e:
        logger.error(f"Ошибка при вводе порога: {e}")
        await message.answer("Произошла ошибка при сохранении")
        await state.clear()
