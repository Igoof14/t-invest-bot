"""Хендлеры раздела «Настройки»: подключение, замена и удаление токена."""

import asyncio
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from common.token_gate import has_token
from common.utils.bot_utils import pluralize_bonds, safe_delete, safe_edit_text
from core.clients.backend.errors import (
    BackendError,
    InvalidToken,
    UpstreamUnavailable,
    UserNotFound,
)
from core.clients.bonds_sync.client import sync_user_bonds, sync_user_events
from features.analytics import EventName, track
from features.base.keyboards import create_main_keyboard
from features.users.repository import BotUserRepository

from .enums import SettingsCallbackData
from .keyboards import (
    create_delete_confirm_keyboard,
    create_settings_keyboard,
    create_token_input_keyboard,
    settings_text,
)

logger = logging.getLogger(__name__)
router = Router()

# Удержание фоновых задач синхронизации портфеля от сборки GC до завершения.
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


async def _sync_events(telegram_id: int) -> None:
    """Догружает историю операций по бумагам пользователя.

    Идёт после облигаций: операции привязаны к уже сохранённым бумагам.
    Пользователю о ней не сообщаем — она нужна расчётам, а не текущему экрану,
    поэтому сбой виден только в логах клиента и в аналитике.

    Args:
        telegram_id: Telegram ID пользователя, для которого запускается синк.

    """
    events_synced = await sync_user_events(telegram_id)
    await track(
        EventName.EVENTS_SYNCED,
        telegram_id=telegram_id,
        count=events_synced,
        ok=events_synced is not None,
    )


async def _sync_portfolio(message: Message, telegram_id: int) -> None:
    """Синхронизирует портфель: сначала список облигаций, затем историю операций.

    Args:
        message: Сообщение с токеном — в его чат уходит уведомление о результате.
        telegram_id: Telegram ID пользователя, для которого запускается синк.

    """
    await _sync_bonds_and_notify(message, telegram_id)
    await _sync_events(telegram_id)


def _schedule_portfolio_sync(message: Message, telegram_id: int) -> None:
    """Запускает синхронизацию портфеля в фоне, не блокируя ответ пользователю.

    Args:
        message: Сообщение с токеном — в его чат уходит уведомление о результате.
        telegram_id: Telegram ID пользователя, для которого запускается синк.

    """
    task = asyncio.create_task(_sync_portfolio(message, telegram_id))
    _SYNC_TASKS.add(task)
    task.add_done_callback(_SYNC_TASKS.discard)


class TokenStates(StatesGroup):
    """Режим ожидания токена."""

    waiting_for_token = State()


async def prompt_for_token(message: Message, state: FSMContext, *, entry: str = "settings") -> None:
    """Показывает экран ввода токена и переводит FSM в ожидание токена.

    Общий шаг для кнопки подключения токена в настройках и финального CTA
    онбординг-воронки.

    Args:
        message: Сообщение, в чат которого отправить инструкцию.
        state: FSM-контекст пользователя.
        entry: Откуда пришёл пользователь — ``onboarding`` или ``settings``.
            Нужен, чтобы считать конверсию двух входов раздельно.

    """
    await message.answer(
        "<b>Токен доступа</b>\n\n"
        "Отправьте ваш <b>Read-only</b> токен сообщением.\n\n"
        "<b>Read-only</b> — токен с правом только на чтение данных. "
        "Он не даёт возможности совершать сделки или переводить средства, "
        "поэтому безопасен для использования в боте.\n\n"
        '<a href="https://developer.tbank.ru/invest/intro/intro/token">Как получить токен</a>',
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=create_token_input_keyboard().as_markup(),
    )
    await state.set_state(TokenStates.waiting_for_token)
    await track(EventName.TOKEN_PROMPT_SHOWN, telegram_id=message.chat.id, entry=entry)


@router.callback_query(F.data == SettingsCallbackData.ADD_TOKEN.value)
async def handle_add_token(callback: CallbackQuery, state: FSMContext) -> None:
    """Открывает экран ввода токена."""
    if isinstance(callback.message, Message):
        await prompt_for_token(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == SettingsCallbackData.TOKEN_INPUT_CANCEL.value)
async def handle_token_input_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Выход из ожидания токена: без него состояние было бы некуда деть."""
    await state.clear()
    if isinstance(callback.message, Message):
        await safe_edit_text(callback.message, "Подключение токена отменено.", reply_markup=None)
    await callback.answer()


@router.callback_query(F.data == SettingsCallbackData.RM_TOKEN.value)
async def handle_rm_token(callback: CallbackQuery) -> None:
    """Спрашивает подтверждение удаления — но только если удалять есть что.

    Кнопка удаления рисуется лишь при подключённом токене, однако сообщение
    могло устареть: пользователь мог удалить токен из другого экрана. Поэтому
    состояние перепроверяется здесь, а не только при отрисовке клавиатуры.
    """
    telegram_id = callback.from_user.id
    if not isinstance(callback.message, Message):
        await callback.answer()
        return

    if not await has_token(telegram_id):
        await safe_edit_text(
            callback.message,
            settings_text(False),
            reply_markup=create_settings_keyboard(False).as_markup(),
        )
        await callback.answer("Токен не подключён — удалять нечего")
        return

    await safe_edit_text(
        callback.message,
        "<b>Удалить токен?</b>\n\n"
        "Портфельные разделы («Купоны», «Погашения», «Оферты») перестанут "
        "работать, а уведомления начнут приходить по всему рынку.",
        reply_markup=create_delete_confirm_keyboard().as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data == SettingsCallbackData.RM_TOKEN_CANCEL.value)
async def handle_rm_token_cancel(callback: CallbackQuery) -> None:
    """Возвращает с подтверждения удаления на экран настроек."""
    if isinstance(callback.message, Message):
        token_connected = await has_token(callback.from_user.id)
        await safe_edit_text(
            callback.message,
            settings_text(token_connected),
            reply_markup=create_settings_keyboard(token_connected).as_markup(),
        )
    await callback.answer("Удаление отменено")


@router.callback_query(F.data == SettingsCallbackData.RM_TOKEN_CONFIRM.value)
async def handle_rm_token_confirm(callback: CallbackQuery) -> None:
    """Удаляет токен и честно сообщает, чем закончилась попытка."""
    telegram_id = callback.from_user.id

    try:
        await BotUserRepository.remove_token(telegram_id, raise_on_error=True)
    except UserNotFound:
        result, notice = "not_found", "Токен и так не был подключён."
    except BackendError as e:
        logger.error(f"Не удалось удалить токен пользователя {telegram_id}: {e}")
        result, notice = "error", "Не удалось удалить токен, попробуйте позже."
    else:
        result, notice = "ok", "Токен удалён."

    await track(EventName.TOKEN_REMOVED, telegram_id=telegram_id, result=result)

    if isinstance(callback.message, Message):
        # Статус перечитываем, а не выводим из результата: при ошибке бэкенда
        # токен мог остаться на месте, и экран не должен утверждать обратное.
        token_connected = await has_token(telegram_id)
        await safe_edit_text(
            callback.message,
            f"{notice}\n\n{settings_text(token_connected)}",
            reply_markup=create_settings_keyboard(token_connected).as_markup(),
        )
    await callback.answer(notice)


@router.message(TokenStates.waiting_for_token)
async def handle_token_message(message: Message, state: FSMContext) -> None:
    """Проверяет и сохраняет присланный токен."""
    telegram_id = message.chat.id
    if not message.text:
        await message.answer("Отправьте токен текстовым сообщением")
        return

    token = message.text.strip()
    logger.info(f"Получен токен от пользователя {telegram_id}")
    # Токен в открытом виде не должен оставаться в истории чата.
    await safe_delete(message)

    # Валидность токена проверяет бэкенд: он спрашивает у T-Invest, прежде чем
    # сохранить. Своей проверки здесь нет намеренно — иначе бот и мини-апп судят
    # о токене каждый по-своему, а бот ещё и требует прямого доступа к брокеру.
    try:
        await BotUserRepository.add_token(telegram_id=telegram_id, token=token)
    except InvalidToken:
        logger.warning(f"Токен пользователя {telegram_id} невалиден")
        outcome = "invalid"
        reply = "Некорректный токен! Проверьте, что скопировали его целиком, и отправьте ещё раз."
    except UpstreamUnavailable:
        outcome = "unavailable"
        reply = (
            "Не удалось проверить токен — сервис T-Invest не ответил. "
            "Попробуйте отправить его ещё раз через пару минут."
        )
    except BackendError:
        # Вердикта о токене мы так и не получили, поэтому для воронки это тот же
        # `unavailable`, что и недоступный брокер: «плохим» токен назвать нельзя.
        logger.warning(f"Не удалось сохранить токен для {telegram_id}")
        outcome = "unavailable"
        reply = "Не удалось сохранить токен, попробуйте отправить его ещё раз."
    else:
        logger.info(f"Токен пользователя {telegram_id} валиден")
        outcome = "valid"
        reply = None

    await track(
        EventName.TOKEN_SUBMITTED,
        telegram_id=telegram_id,
        valid=outcome == "valid",
        result=outcome,
    )

    if reply is not None:
        await message.answer(
            reply,
            reply_markup=create_token_input_keyboard().as_markup(),
        )
        return

    await track(EventName.TOKEN_CONNECTED, telegram_id=telegram_id)
    await state.clear()
    await message.answer(
        "Токен успешно сохранён! Синхронизирую список облигаций...",
        reply_markup=create_main_keyboard(),
    )
    _schedule_portfolio_sync(message, telegram_id)
