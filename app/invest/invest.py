"""Функции для работы с T-Invest API."""

from .tbank_client import TBankClient


async def check_token(token: str) -> bool:
    """Проверяет, что токен действителен.

    Args:
        token: API токен

    Returns:
        True если токен валиден

    """
    try:
        async with TBankClient(token) as client:
            await client.get_info()
        return True
    except Exception:
        return False
