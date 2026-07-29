"""Гейт разделов, которым нужен портфель пользователя.

Без токена бот остаётся полезным: уведомления приходят по всему рынку
(см. :mod:`common.scope`), и настраивать их можно как обычно. А вот экраны
«Купоны», «Погашения» и «Оферты» строятся из позиций портфеля — показывать там
нечего, пока токен не подключён. Такие хендлеры зовут :func:`has_token` и
отвечают :data:`TOKEN_REQUIRED`.
"""

from __future__ import annotations

import logging

from core.clients.backend import users as users_api
from core.clients.backend.errors import BackendError, UserNotFound

logger = logging.getLogger(__name__)

# Заглушка для портфельных разделов: объясняет отказ и показывает выход.
TOKEN_REQUIRED = (
    "🔒 <b>Доступно только с токеном</b>\n\n"
    "Этот раздел строится по вашему портфелю. Подключите токен в «Настройках» — "
    "и данные появятся.\n\n"
    "<i>Уведомления работают и без токена — по всему рынку.</i>"
)


async def has_token(telegram_id: int) -> bool:
    """Подключён ли токен T-Invest.

    При сбое бэкенда отвечает ``True``: гейт лишь предупреждает, и лучше пустить
    пользователя дальше — там уже свой разбор ошибок — чем закрыть раздел тому,
    у кого токен есть.
    """
    try:
        return await users_api.get_token(telegram_id) is not None
    except UserNotFound:
        # Пользователя нет в бэкенде — токена тем более нет.
        return False
    except BackendError as e:
        logger.error(f"Не удалось проверить токен пользователя {telegram_id}: {e}")
        return True
