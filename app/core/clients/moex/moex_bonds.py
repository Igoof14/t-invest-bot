"""Модуль для работы облигациями через API Московской биржи."""

import asyncio
import logging
from datetime import date
from typing import Any

import aiohttp
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class MoexClient:
    """Клиент для взаимодействия с API MOEX."""

    BASE_URL = "https://iss.moex.com/iss"

    def __init__(
        self,
        concurrency_limit: int = 10,
        timeout: int = 10,
    ):
        """Инициализация клиента."""
        self._session: aiohttp.ClientSession | None = None
        self._semaphore = asyncio.Semaphore(concurrency_limit)
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    async def __aenter__(self):
        """Асинхронный контекстный менеджер."""
        self._session = aiohttp.ClientSession(
            timeout=self._timeout,
        )
        return self

    async def __aexit__(self, *args):
        """Закрытие сессии."""
        if self._session:
            await self._session.close()

    async def _request_json(
        self,
        endpoint: str,
    ) -> dict[str, Any]:
        if self._session is None:
            raise RuntimeError("Client is not initialized. Use 'async with MoexClient()'")

        url = f"{self.BASE_URL}{endpoint}"

        async with self._semaphore:
            async with self._session.get(url) as response:
                response.raise_for_status()
                return await response.json()

    @staticmethod
    def _description_fields(data: dict[str, Any]) -> dict[str, Any]:
        """Преобразует блок ``description`` в словарь ``name -> value``."""
        desc = data.get("description", {})
        columns = desc.get("columns", [])
        rows = desc.get("data", [])
        if "name" not in columns or "value" not in columns:
            return {}
        name_idx = columns.index("name")
        value_idx = columns.index("value")
        return {row[name_idx]: row[value_idx] for row in rows}

    async def _get_emitter_id(self, secid: str) -> tuple[int | None, str | None]:
        """Возвращает ``(emitter_id, name)`` для бумаги по её ISIN/secid."""
        data = await self._request_json(f"/securities/{secid.upper()}.json?iss.meta=off")
        fields = self._description_fields(data)

        raw_id = fields.get("EMITTER_ID")
        name = fields.get("NAME")
        if raw_id is None:
            return None, name
        try:
            return int(raw_id), name
        except (TypeError, ValueError):
            return None, name
