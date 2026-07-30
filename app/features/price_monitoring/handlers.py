import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from common.utils.bot_utils import safe_delete, safe_edit_text
from features.analytics import EventName, track
from features.menu import status_text

from .enums import PriceAlertCallbackData
from .keyboards import create_thresholds_keyboard
from .menu import render
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
    """Показывает раздел мониторинга цен (возврат из настройки порогов)."""
    try:
        text, markup = await render(callback.from_user.id)
        if callback.message and isinstance(callback.message, Message):
            await safe_edit_text(callback.message, text, reply_markup=markup)
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
        await track(
            EventName.ALERT_TOGGLED,
            telegram_id=telegram_id,
            action="price",
            feature="price",
            enabled=new_state,
        )

        text, markup = await render(telegram_id)
        if callback.message and isinstance(callback.message, Message):
            await safe_edit_text(callback.message, text, reply_markup=markup)

        await callback.answer("Мониторинг цен: " + status_text(new_state))

    except Exception as e:
        logger.error(f"Ошибка при переключении уведомлений: {e}")
        await callback.answer("Произошла ошибка")


@router.callback_query(F.data == PriceAlertCallbackData.PRICE_ALERTS_SETTINGS.value + "_thresholds")
async def handle_thresholds_menu(callback: CallbackQuery) -> None:
    """Показывает меню настройки порогов."""
    try:
        telegram_id = callback.from_user.id
        settings = await AlertSettingsRepository.get(telegram_id)

        # Кнопка порогов есть только при включённых уведомлениях; сюда можно попасть
        # лишь по устаревшему сообщению.
        if not settings.alerts_enabled:
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
            await safe_edit_text(callback.message, message_text, reply_markup=builder.as_markup())
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

        prompt = prompts.get(threshold_type) if threshold_type else None
        new_state = states.get(threshold_type) if threshold_type else None

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


# Порог «умеренного» движения обязан быть строго ниже «сильного»: иначе сильное
# движение никогда не сработает, а экран покажет пару вроде «Умеренное 10% /
# Сильное 2%», которая ничего не значит.
_THRESHOLD_PAIRS = {
    "drop_warning_threshold": ("drop_critical_threshold", "ниже", "порога сильного падения"),
    "drop_critical_threshold": ("drop_warning_threshold", "выше", "порога умеренного падения"),
    "rise_warning_threshold": ("rise_critical_threshold", "ниже", "порога сильного роста"),
    "rise_critical_threshold": ("rise_warning_threshold", "выше", "порога умеренного роста"),
}


async def _threshold_conflict(telegram_id: int, field: str, value: float) -> str | None:
    """Возвращает текст ошибки, если новое значение ломает пару порогов.

    Args:
        telegram_id: Чьи текущие пороги проверять.
        field: Имя изменяемого поля настроек.
        value: Новое значение в процентах.

    Returns:
        Сообщение для пользователя или ``None``, если конфликта нет.

    """
    other_field, direction, other_title = _THRESHOLD_PAIRS[field]
    other_value = getattr(await AlertSettingsRepository.get(telegram_id), other_field)
    ok = value < other_value if direction == "ниже" else value > other_value
    if ok:
        return None
    return f"Значение должно быть {direction} {other_title} ({other_value}%). Введите другое число."


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
            conflict = await _threshold_conflict(telegram_id, field, value)
            if conflict:
                await message.answer(conflict)
                return

            if not await AlertSettingsRepository.update(telegram_id, **{field: value}):
                # Состояние оставляем: ввод можно повторить, не проходя меню заново.
                await message.answer(
                    "Не удалось сохранить порог, попробуйте отправить значение ещё раз."
                )
                return
            await track(
                EventName.ALERT_SETTING_CHANGED,
                telegram_id=telegram_id,
                action=f"price:{field}",
                feature="price",
                field=field,
                value=value,
            )

            state_data = await state.get_data()
            prompt_message_id = state_data.get("prompt_message_id")

            if prompt_message_id and isinstance(message.bot, Bot):
                try:
                    await message.bot.delete_message(
                        chat_id=message.chat.id, message_id=prompt_message_id
                    )
                except TelegramAPIError as e:
                    logger.info(f"Не удалось удалить приглашение к вводу порога: {e}")

            await safe_delete(message)

            await message.answer(f"Порог успешно изменён на {value}%")
            await state.clear()
        else:
            await message.answer("Неизвестное состояние")
            await state.clear()

    except Exception as e:
        logger.error(f"Ошибка при вводе порога: {e}")
        await message.answer("Произошла ошибка при сохранении")
        await state.clear()
