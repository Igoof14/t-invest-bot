"""Клиент синхронизации портфеля пользователя через Cloud Run сервис.

Сервис отдаёт два эндпоинта: список облигаций (`/sync/{telegram_id}`) и историю
операций по нему (`/sync/events/{telegram_id}`). Вызываются они одинаково —
разница только в пути, поле счётчика и слове в логах.
"""

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


async def _sync(path: str, telegram_id: int, count_field: str, what: str) -> int | None:
    """Дёргает эндпоинт синхронизации и возвращает счётчик из ответа.

    Авторизация выполняется OIDC id-token'ом, полученным через metadata server
    GCE — сервис-аккаунт инстанса должен иметь роль `roles/run.invoker`
    на целевом Cloud Run сервисе.

    Args:
        path: Путь эндпоинта от корня сервиса, например ``/sync/123``.
        telegram_id: Telegram ID пользователя — нужен только для логов.
        count_field: Поле ответа со счётчиком синхронизированных записей.
        what: Что синхронизируем, в родительном падеже — для логов.

    Returns:
        Значение ``count_field`` из ответа или ``None``, если синхронизация
        не выполнена.

    """
    base_url = config.bonds_sync_url
    if not base_url:
        logger.warning(f"BONDS_SYNC_URL не задан — синхронизация {what} пропущена")
        return None

    base_url = base_url.rstrip("/")
    url = f"{base_url}{path}"

    try:
        token = await asyncio.to_thread(_fetch_id_token, base_url)
    except GoogleAuthError:
        logger.error(
            f"Не удалось получить OIDC id-token для синхронизации {what} {telegram_id}",
            exc_info=True,
        )
        return None

    if not token:
        logger.error(
            f"Metadata server не вернул OIDC id-token для синхронизации {what} {telegram_id}"
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
            f"Ошибка синхронизации {what} для пользователя {telegram_id}",
            exc_info=True,
        )
        return None

    synced = payload.get(count_field)
    if not isinstance(synced, int):
        logger.error(
            f"Сервис синхронизации не вернул {count_field} "
            f"для пользователя {telegram_id}: {payload}"
        )
        return None

    logger.info(f"Синхронизировано {what} для пользователя {telegram_id}: {synced}")
    return synced


async def sync_user_bonds(telegram_id: int) -> int | None:
    """Запускает синхронизацию списка облигаций пользователя.

    Args:
        telegram_id: Telegram ID пользователя.

    Returns:
        Количество синхронизированных облигаций (`bonds_synced` из ответа)
        или ``None``, если синхронизация не выполнена.

    """
    return await _sync(f"/sync/{telegram_id}", telegram_id, "bonds_synced", "облигаций")


async def sync_user_events(telegram_id: int) -> int | None:
    """Запускает синхронизацию истории операций пользователя.

    Args:
        telegram_id: Telegram ID пользователя.

    Returns:
        Количество синхронизированных операций (`events_synced` из ответа)
        или ``None``, если синхронизация не выполнена.

    """
    return await _sync(f"/sync/events/{telegram_id}", telegram_id, "events_synced", "операций")
