"""Дополнительные функции для работы с T-Invest API."""

import logging
from enum import Enum

from grpc import StatusCode
from t_tech.invest import AsyncClient
from t_tech.invest.exceptions import AioRequestError, RequestError

logger = logging.getLogger(__name__)

# gRPC-коды, при которых виноват именно токен, а не канал связи.
_TOKEN_REJECTED = frozenset(
    {
        StatusCode.UNAUTHENTICATED,
        StatusCode.PERMISSION_DENIED,
        StatusCode.INVALID_ARGUMENT,
    }
)


class TokenCheck(Enum):
    """Итог проверки токена.

    Три исхода, а не два: сбой сети до T-Invest — это не «токен плохой».
    Раньше оба случая сливались в ``False``, и пользователь с рабочим токеном
    видел «Некорректный токен!», а воронка получала ложный ``valid=False``.
    """

    VALID = "valid"
    INVALID = "invalid"
    UNAVAILABLE = "unavailable"


async def check_token(token: str) -> TokenCheck:
    """Проверяет, что токен действителен.

    Args:
        token: API токен.

    Returns:
        ``VALID`` — токен принят; ``INVALID`` — T-Invest отверг токен;
        ``UNAVAILABLE`` — проверить не удалось (сеть, таймаут, сбой сервиса).

    """
    try:
        async with AsyncClient(token) as client:
            await client.users.get_info()
    except (AioRequestError, RequestError) as e:
        if e.code in _TOKEN_REJECTED:
            logger.warning(f"T-Invest отверг токен: {e.code}")
            return TokenCheck.INVALID
        # UNAVAILABLE, DEADLINE_EXCEEDED, RESOURCE_EXHAUSTED — проблема не в токене.
        logger.error(f"Не удалось проверить токен T-Invest: {e.code}")
        return TokenCheck.UNAVAILABLE
    except Exception:
        logger.error("Не удалось проверить токен T-Invest", exc_info=True)
        return TokenCheck.UNAVAILABLE
    return TokenCheck.VALID


def to_float(value) -> float:
    """Конвертирует в float."""
    return value.units + value.nano / 1e9
