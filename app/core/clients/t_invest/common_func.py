"""Дополнительные функции для работы с T-Invest API."""

import logging

from t_tech.invest import AsyncClient

logger = logging.getLogger(__name__)


async def check_token(token: str) -> bool:
    """Проверяет, что токен действителен.

    Args:
        token: API токен

    Returns:
        True если токен валиден

    """
    try:
        async with AsyncClient(token) as client:
            await client.users.get_info()
        return True
    except Exception:
        logger.warning("Проверка токена T-Invest не удалась", exc_info=True)
        return False


def to_float(value) -> float:
    """Конвертирует в float."""
    return value.units + value.nano / 1e9
