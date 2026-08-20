"""Хендлеры раздела «Настройки»: подключение токена через мини-апп.

Добавление, замена и удаление токена происходят только в мини-аппе — там уже
есть форма на каждого брокера (`TokenCard`). Бот лишь показывает кнопку,
открывающую нужный экран мини-аппа.
"""

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message, WebAppInfo
from common.token_gate import has_token
from common.utils.bot_utils import safe_edit_text
from core.config import config
from features.analytics import EventName, track

from .enums import SettingsCallbackData
from .keyboards import create_open_miniapp_keyboard, create_settings_keyboard, settings_text

logger = logging.getLogger(__name__)
router = Router()

_MINIAPP_UNAVAILABLE = (
    "Подключение токена сейчас недоступно — приложение временно не отвечает. "
    "Попробуйте немного позже."
)


async def prompt_open_miniapp(message: Message, *, entry: str = "settings") -> None:
    """Показывает кнопку открытия мини-аппа для подключения токена.

    Общий шаг для кнопки подключения токена в настройках и финального CTA
    онбординг-воронки.

    Args:
        message: Сообщение, в чат которого отправить кнопку.
        entry: Откуда пришёл пользователь — ``onboarding`` или ``settings``.
            Нужен, чтобы считать конверсию двух входов раздельно.

    """
    if not config.miniapp_url:
        logger.warning("Не задан MINIAPP_URL — кнопка подключения токена недоступна")
        await message.answer(_MINIAPP_UNAVAILABLE)
        return

    await message.answer(
        "<b>Токен доступа</b>\n\n"
        "Токен подключается в приложении: выберите брокера и вставьте "
        "<b>Read-only</b> токен — с правом только на чтение, без возможности "
        "совершать сделки или переводить средства.",
        parse_mode="HTML",
        reply_markup=create_open_miniapp_keyboard(
            WebAppInfo(url=f"{config.miniapp_url.rstrip('/')}/profile")
        ).as_markup(),
    )
    await track(EventName.TOKEN_PROMPT_SHOWN, telegram_id=message.chat.id, entry=entry)


@router.callback_query(F.data == SettingsCallbackData.ADD_TOKEN.value)
async def handle_add_token(callback: CallbackQuery) -> None:
    """Показывает кнопку открытия мини-аппа."""
    if isinstance(callback.message, Message):
        await prompt_open_miniapp(callback.message)
    await callback.answer()


@router.callback_query(F.data == SettingsCallbackData.BACK_TO_SETTINGS.value)
async def handle_back_to_settings(callback: CallbackQuery) -> None:
    """Возвращает с экрана кнопки мини-аппа на экран настроек."""
    if isinstance(callback.message, Message):
        token_connected = await has_token(callback.from_user.id)
        await safe_edit_text(
            callback.message,
            settings_text(token_connected),
            reply_markup=create_settings_keyboard(token_connected).as_markup(),
        )
    await callback.answer()
