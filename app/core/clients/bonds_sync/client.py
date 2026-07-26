"""Клиент для синхронизации облигаций пользователя через Cloud Run сервис."""

import asyncio
import logging

import aiohttp
from core.config import config
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.oauth2.id_token import fetch_id_token

logger = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=30)


def _fetch_id_token(audience: str) -> str | None:
    """Запрашивает OIDC id-token у metadata server GCE (блокирующий вызов)."""
    return fetch_id_token(Request(), audience)


async def sync_user_bonds(telegram_id: int) -> int | None:
    """Запускает синхронизацию списка облигаций пользователя в Cloud Run сервисе.

    Авторизация выполняется OIDC id-token'ом, полученным через metadata server
    GCE — сервис-аккаунт инстанса должен иметь роль `roles/run.invoker`
    на целевом Cloud Run сервисе.

    Args:
        telegram_id: Telegram ID пользователя.

    Returns:
        Количество синхронизированных облигаций (`bonds_synced` из ответа)
        или ``None``, если синхронизация не выполнена.

    """
    base_url = config.bonds_sync_url
    if not base_url:
        logger.warning("BONDS_SYNC_URL не задан — синхронизация облигаций пропущена")
        return None

    base_url = base_url.rstrip("/")
    url = f"{base_url}/sync/{telegram_id}"

    try:
        token = await asyncio.to_thread(_fetch_id_token, base_url)
    except GoogleAuthError:
        logger.error(
            f"Не удалось получить OIDC id-token для синхронизации облигаций {telegram_id}",
            exc_info=True,
        )
        return None

    if not token:
        logger.error(
            f"Metadata server не вернул OIDC id-token для синхронизации облигаций {telegram_id}"
        )
        return None

    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with (
            aiohttp.ClientSession(timeout=_TIMEOUT) as session,
            session.post(url, headers=headers) as resp,
        ):
            resp.raise_for_status()
            payload = await resp.json()
    except (aiohttp.ClientError, TimeoutError, ValueError):
        logger.error(
            f"Ошибка синхронизации облигаций для пользователя {telegram_id}",
            exc_info=True,
        )
        return None

    bonds_synced = payload.get("bonds_synced")
    if not isinstance(bonds_synced, int):
        logger.error(
            f"Сервис синхронизации не вернул bonds_synced для пользователя {telegram_id}: {payload}"
        )
        return None

    logger.info(f"Синхронизировано облигаций для пользователя {telegram_id}: {bonds_synced}")
    return bonds_synced
