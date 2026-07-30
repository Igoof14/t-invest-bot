import logging
import re
from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from common.utils.bot_utils import pluralize_days, safe_delete, safe_edit_text
from features.analytics import EventName, track
from features.menu import nav_button, status_text

from .keyboards import create_offer_alert_setting_keyboard
from .menu import SECTION_KEY, render
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
        await track(
            EventName.ALERT_TOGGLED,
            telegram_id=telegram_id,
            action="offer",
            feature="offer",
            enabled=new_state,
        )

        text, markup = await render(telegram_id)
        if callback.message and isinstance(callback.message, Message):
            await safe_edit_text(callback.message, text, reply_markup=markup)

        await callback.answer("Оферты: " + status_text(new_state))

    except Exception as e:
        logger.error(f"Ошибка при переключении уведомлений об офертах: {e}")
        await callback.answer("Произошла ошибка")


@router.callback_query(OfferAlertCallback.filter(F.action == "setting"))
async def handle_offer_alert_setting(callback: CallbackQuery) -> None:
    """Обработчик для кнопки настроек уведомлений об офертах."""
    try:
        telegram_id = callback.from_user.id
        settings = await OfferSettingsRepository.get(telegram_id)

        # Настраивать выключенные напоминания бессмысленно: экран показывал бы
        # голый заголовок и кнопки, которые пишут в никуда. Кнопка «Настроить»
        # при выключенных уведомлениях не рисуется — сюда можно попасть только
        # по устаревшему сообщению.
        if not settings.alerts_enabled:
            await callback.answer("Сначала включите уведомления")
            return

        message_text = (
            f"<b>Настройки уведомлений об офертах</b>\n\n"
            f"<b>Текущие настройки:</b>\n\n"
            f"Первое напоминание за: {settings.first_alert} "
            f"{pluralize_days(settings.first_alert)}\n"
            f"Второе напоминание за: {settings.second_alert} "
            f"{pluralize_days(settings.second_alert)}\n"
            f"Время уведомления: {str(settings.notification_time)[:-3]} МСК\n\n"
            f"Выберите, что настроить:"
        )

        builder = create_offer_alert_setting_keyboard()
        builder.row(nav_button(SECTION_KEY))

        if callback.message and isinstance(callback.message, Message):
            await safe_edit_text(callback.message, message_text, reply_markup=builder.as_markup())
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при показе меню уведомлений: {e}")
        await callback.answer("Произошла ошибка")


class OfferAlertStates(StatesGroup):
    """Состояния для управления уведомлениями об офертах."""

    waiting_for_first = State()
    waiting_for_second = State()
    waiting_for_time = State()


_PROMPTS = {
    "set_first": (
        OfferAlertStates.waiting_for_first,
        "Введите, за сколько дней до оферты напомнить в первый раз (целое число от 1 до 50):",
    ),
    "set_second": (
        OfferAlertStates.waiting_for_second,
        "Введите, за сколько дней напомнить во второй раз "
        "(целое число, меньше первого напоминания):",
    ),
    "set_time": (
        OfferAlertStates.waiting_for_time,
        "Введите время напоминания в формате ЧЧ:ММ (например, 15:30):",
    ),
}

# Максимум дней, за которые бот напоминает об оферте.
_MAX_ALERT_DAYS = 50


@router.callback_query(OfferAlertCallback.filter(F.action.in_(list(_PROMPTS))))
async def handle_set_settings(
    callback: CallbackQuery, callback_data: OfferAlertCallback, state: FSMContext
) -> None:
    """Спрашивает новое значение выбранной настройки."""
    try:
        target = _PROMPTS.get(callback_data.action)
        if target is None or not isinstance(callback.message, Message):
            await callback.answer()
            return

        new_state, prompt = target
        await callback.message.answer(prompt)
        await state.set_state(new_state)
    except Exception as e:
        logger.error(f"Ошибка при открытии ввода настройки оферт: {e}")
        await callback.answer("Произошла ошибка")
        return
    # Квитируем нажатие для всех трёх кнопок, а не только для «Время
    # уведомления»: иначе на остальных часики крутились до таймаута.
    await callback.answer()


def _parse_days(text: str) -> tuple[int | None, str | None]:
    """Разбирает количество дней; возвращает ``(значение, текст ошибки)``."""
    if not text.isdigit():
        return None, "Введите целое число."
    value = int(text)
    if not 0 < value <= _MAX_ALERT_DAYS:
        return (
            None,
            f"Число должно быть больше 0 и не больше {_MAX_ALERT_DAYS}. Попробуйте ещё раз:",
        )
    return value, None


async def _save(
    message: Message, state: FSMContext, *, field: str, value: object, done: str
) -> None:
    """Сохраняет одно поле настроек и отвечает по фактическому результату.

    При отказе бэкенда состояние сохраняется: пользователь может отправить
    значение повторно, не проходя меню заново. Раньше здесь безусловно
    печаталось «успешно установлено», даже когда запись не прошла.
    """
    telegram_id = message.chat.id
    if not await OfferSettingsRepository.update(telegram_id, **{field: value}):
        await message.answer(
            "Не удалось сохранить настройку, попробуйте отправить значение ещё раз."
        )
        return

    await track(
        EventName.ALERT_SETTING_CHANGED,
        telegram_id=telegram_id,
        action=f"offer:{field}",
        feature="offer",
        field=field,
        value=value if isinstance(value, int) else None,
    )
    await safe_delete(message)
    await message.answer(done)
    await state.clear()


@router.message(OfferAlertStates.waiting_for_first)
async def process_first_alert(message: Message, state: FSMContext) -> None:
    """Обработчик для установки первого напоминания."""
    value, error = _parse_days(message.text.strip() if message.text else "")
    if value is None:
        await message.answer(error or "")
        return

    settings = await OfferSettingsRepository.get(message.chat.id)
    if value <= settings.second_alert:
        await message.answer(
            f"Первое напоминание должно быть раньше второго "
            f"({settings.second_alert} {pluralize_days(settings.second_alert)}). "
            f"Введите число больше {settings.second_alert}:"
        )
        return

    await _save(
        message,
        state,
        field="first_alert",
        value=value,
        done=f"Первое напоминание: за {value} {pluralize_days(value)} до оферты.",
    )


@router.message(OfferAlertStates.waiting_for_second)
async def process_second_alert(message: Message, state: FSMContext) -> None:
    """Обработчик для установки второго напоминания."""
    value, error = _parse_days(message.text.strip() if message.text else "")
    if value is None:
        await message.answer(error or "")
        return

    # Промпт обещал «меньше первого» — раньше это нигде не проверялось, и пара
    # «Первое за 5 дней / Второе за 40 дней» спокойно сохранялась.
    settings = await OfferSettingsRepository.get(message.chat.id)
    if value >= settings.first_alert:
        await message.answer(
            f"Второе напоминание должно быть позже первого "
            f"({settings.first_alert} {pluralize_days(settings.first_alert)}). "
            f"Введите число меньше {settings.first_alert}:"
        )
        return

    await _save(
        message,
        state,
        field="second_alert",
        value=value,
        done=f"Второе напоминание: за {value} {pluralize_days(value)} до оферты.",
    )


@router.message(OfferAlertStates.waiting_for_time)
async def process_time_alert(message: Message, state: FSMContext) -> None:
    """Обработчик для установки времени напоминания."""
    text = message.text.strip() if message.text else ""

    if not re.match(r"^([01][0-9]|2[0-3]):[0-5][0-9]$", text):
        await message.answer(
            "Неверный формат времени! Введите в формате ЧЧ:ММ (например, 09:00 или 18:30):"
        )
        return

    await _save(
        message,
        state,
        field="notification_time",
        value=datetime.strptime(text, "%H:%M").time(),
        done=f"Время напоминания: {text} МСК.",
    )
