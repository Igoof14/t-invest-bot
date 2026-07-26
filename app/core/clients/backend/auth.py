"""OIDC-авторизация вызовов приватного Cloud Run сервиса `backend`.

Cloud Run сам валидирует id-token на границе сервиса, поэтому боту достаточно
получить токен у metadata server (в GCP) или из application default credentials
(локально, после `gcloud auth application-default login`) и приложить его
заголовком ``Authorization: Bearer``.

Токен живёт около часа, поэтому кэшируется по audience и обновляется заранее —
за :data:`_REFRESH_MARGIN` до `exp`.
"""

import asyncio
import logging
import time

from google.auth import jwt
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.oauth2.id_token import fetch_id_token

from .errors import BackendAuthError

logger = logging.getLogger(__name__)

# За сколько секунд до `exp` считаем токен просроченным и запрашиваем новый.
_REFRESH_MARGIN = 300

# Запасной срок жизни, если `exp` из токена прочитать не удалось.
_FALLBACK_TTL = 1800

_LOCAL_AUTH_HINT = (
    "Вне GCP нужны credentials сервис-аккаунта: "
    "`gcloud auth application-default login "
    "--impersonate-service-account=772435034855-compute@developer.gserviceaccount.com` "
    "или GOOGLE_APPLICATION_CREDENTIALS с ключом SA. "
    "У аккаунта должна быть роль roles/run.invoker на целевом сервисе."
)

_cache: dict[str, tuple[str, float]] = {}
_lock = asyncio.Lock()


def _fetch_id_token(audience: str) -> str | None:
    """Запрашивает OIDC id-token (блокирующий вызов)."""
    return fetch_id_token(Request(), audience)


def _expires_at(token: str) -> float:
    """Момент истечения токена по его `exp`; при ошибке — запасной срок."""
    try:
        payload = jwt.decode(token, verify=False)
        return float(payload["exp"])
    except (ValueError, KeyError, TypeError):
        logger.warning("Не удалось прочитать exp из id-token, используем запасной TTL")
        return time.time() + _FALLBACK_TTL


async def get_id_token(audience: str) -> str:
    """Возвращает актуальный OIDC id-token для указанного audience.

    Args:
        audience: Базовый URL целевого Cloud Run сервиса, без пути.

    Returns:
        Валидный id-token — из кэша или свежезапрошенный.

    Raises:
        BackendAuthError: Токен получить не удалось.

    """
    cached = _cache.get(audience)
    if cached and cached[1] - _REFRESH_MARGIN > time.time():
        return cached[0]

    async with _lock:
        # Пока ждали блокировку, токен мог обновить другой запрос.
        cached = _cache.get(audience)
        if cached and cached[1] - _REFRESH_MARGIN > time.time():
            return cached[0]

        try:
            token = await asyncio.to_thread(_fetch_id_token, audience)
        except GoogleAuthError as exc:
            raise BackendAuthError(
                f"Не удалось получить OIDC id-token для {audience}: {exc}. {_LOCAL_AUTH_HINT}"
            ) from exc

        if not token:
            raise BackendAuthError(f"Пустой OIDC id-token для {audience}. {_LOCAL_AUTH_HINT}")

        _cache[audience] = (token, _expires_at(token))
        logger.info(f"Получен новый OIDC id-token для {audience}")
        return token


async def auth_headers(audience: str) -> dict[str, str]:
    """Заголовок ``Authorization`` с актуальным id-token'ом.

    Raises:
        BackendAuthError: Токен получить не удалось.

    """
    return {"Authorization": f"Bearer {await get_id_token(audience)}"}


def reset_token_cache() -> None:
    """Сбрасывает кэш токенов (используется в тестах)."""
    _cache.clear()
