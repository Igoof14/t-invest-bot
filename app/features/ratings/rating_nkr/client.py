"""Асинхронный клиент к сайту НКР (ratings.ru)."""

from __future__ import annotations

import asyncio
import logging

import aiohttp
from features.ratings.events import RatingEvent, ReleaseStub

from . import config
from .parser import parse_listing, parse_release

logger = logging.getLogger(__name__)


class NkrClient:
    """Клиент для перечисления и загрузки релизов рейтингов НКР."""

    def __init__(
        self,
        base_url: str = config.BASE_URL,
        concurrency_limit: int = config.CONCURRENCY,
        timeout: int = config.TIMEOUT,
    ) -> None:
        """Инициализация клиента."""
        self._base = base_url.rstrip("/")
        self._session: aiohttp.ClientSession | None = None
        self._semaphore = asyncio.Semaphore(concurrency_limit)
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    async def __aenter__(self) -> NkrClient:
        """Открывает HTTP-сессию с браузерным User-Agent."""
        self._session = aiohttp.ClientSession(
            timeout=self._timeout, headers={"User-Agent": config.USER_AGENT}
        )
        return self

    async def __aexit__(self, *args: object) -> None:
        """Закрывает HTTP-сессию."""
        if self._session:
            await self._session.close()

    @property
    def _client(self) -> aiohttp.ClientSession:
        if self._session is None:
            raise RuntimeError("Клиент не инициализирован. Используйте 'async with NkrClient()'")
        return self._session

    async def iter_release_stubs(self, max_items: int = config.MAX_ITEMS) -> list[ReleaseStub]:
        """Возвращает верхние ``max_items`` листинговых записей (новейшие сверху)."""
        url = f"{self._base}{config.LIST_PATH}"
        try:
            async with self._semaphore, self._client.get(url) as response:
                response.raise_for_status()
                html = await response.text()
        except Exception as e:
            logger.error(f"Ошибка при загрузке листинга НКР: {e}")
            return []

        return parse_listing(html)[:max_items]

    async def fetch_release(self, stub: ReleaseStub) -> RatingEvent | None:
        """Загружает и парсит страницу одного релиза."""
        async with self._semaphore, self._client.get(stub.url) as response:
            response.raise_for_status()
            html = await response.text()
        return parse_release(html, stub)

    async def fetch_many(self, stubs: list[ReleaseStub]) -> list[RatingEvent]:
        """Конкурентно загружает страницы релизов, пропуская ошибочные."""
        tasks = [self.fetch_release(stub) for stub in stubs]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        events: list[RatingEvent] = []
        for stub, result in zip(stubs, results, strict=False):
            if isinstance(result, BaseException):
                logger.error(f"Ошибка при загрузке релиза {stub.url}: {result}")
            elif result is not None:
                events.append(result)
        return events
