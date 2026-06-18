"""Клиент к ленте НРД (nsddata.ru) через headless-браузер Playwright.

Страницы новостей НРД защищены JS-антиботом (страница «Redirect» вычисляет cookie
и перезагружается), поэтому обычный HTTP-запрос получает 403. Playwright исполняет
челлендж как настоящий браузер. Поиск по ISIN (`?text=<ISIN>`) отдаёт только новости
по конкретной бумаге, что позволяет точечно проверять купоны без обхода всей ленты.
"""

from __future__ import annotations

import logging
from datetime import date
from types import TracebackType
from urllib.parse import quote, urlsplit

from playwright.async_api import (
    Browser,
    BrowserContext,
    ProxySettings,
    async_playwright,
)

logger = logging.getLogger(__name__)

_BASE = "https://nsddata.ru"
_NEWS = f"{_BASE}/ru/news"
# Заголовок страницы-заглушки антибота, пока челлендж не пройден.
_CHALLENGE_TITLE = "Redirect"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


class NsdAccessError(RuntimeError):
    """Не удалось получить страницу НРД (антибот не пройден или таймаут)."""


def to_playwright_proxy(proxy: str | None) -> ProxySettings | None:
    """Преобразует URL прокси в формат настроек прокси Playwright.

    Args:
        proxy: URL вида ``http://[user:pass@]host:port`` или ``None``.

    Returns:
        ``ProxySettings`` с ``server``/``username``/``password`` или ``None`` для
        прямого соединения.

    """
    if not proxy:
        return None
    parts = urlsplit(proxy)
    result: ProxySettings = {"server": f"{parts.scheme}://{parts.hostname}:{parts.port}"}
    if parts.username:
        result["username"] = parts.username
    if parts.password:
        result["password"] = parts.password
    return result


class NsdClient:
    """Асинхронный клиент к ленте НРД поверх Playwright.

    Браузер и контекст создаются один раз на время жизни клиента: cookie антибота
    переиспользуются между запросами, поэтому челлендж проходится только при первом
    обращении. Используется как асинхронный контекстный менеджер::

        async with NsdClient(proxy) as client:
            html = await client.search_by_isin("RU000A105P23")
            card = await client.fetch_card(1409937)
    """

    def __init__(
        self,
        proxy: str | None = None,
        *,
        headless: bool = True,
        nav_timeout_ms: int = 60_000,
        challenge_timeout_ms: int = 25_000,
        settle_ms: int = 1_500,
    ) -> None:
        """Инициализирует клиент.

        Args:
            proxy: URL прокси или ``None`` (прямое соединение).
            headless: Запускать браузер без интерфейса.
            nav_timeout_ms: Таймаут навигации, мс.
            challenge_timeout_ms: Сколько ждать прохождения антибота, мс.
            settle_ms: Доп. пауза после прохождения челленджа, мс.

        """
        self._proxy = proxy
        self._headless = headless
        self._nav_timeout_ms = nav_timeout_ms
        self._challenge_timeout_ms = challenge_timeout_ms
        self._settle_ms = settle_ms
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def __aenter__(self) -> NsdClient:
        """Запускает Playwright и браузер, возвращает готовый клиент."""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self._headless,
            proxy=to_playwright_proxy(self._proxy),
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._context = await self._browser.new_context(locale="ru-RU", user_agent=_USER_AGENT)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Закрывает браузер и останавливает Playwright."""
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()

    async def _open(self, url: str) -> str:
        """Открывает URL, дожидается прохождения антибота и возвращает HTML.

        Args:
            url: Абсолютный URL страницы НРД.

        Returns:
            HTML-содержимое страницы после прохождения челленджа.

        Raises:
            NsdAccessError: Если антибот не пройден за отведённое время.

        """
        if self._context is None:
            raise NsdAccessError("клиент не инициализирован (используйте async with)")

        page = await self._context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=self._nav_timeout_ms)
            try:
                await page.wait_for_function(
                    f"document.title && document.title !== {_CHALLENGE_TITLE!r}",
                    timeout=self._challenge_timeout_ms,
                )
            except Exception as e:  # noqa: BLE001 — playwright TimeoutError и пр.
                raise NsdAccessError(f"антибот НРД не пройден: {url}") from e
            await page.wait_for_timeout(self._settle_ms)
            return await page.content()
        finally:
            await page.close()

    async def search_by_isin(
        self,
        isin: str,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> str:
        """Возвращает HTML страницы поиска новостей НРД по ISIN.

        По умолчанию НРД отдаёт новости только за последнюю неделю; диапазон дат
        задаётся параметрами ``date_from``/``date_to``.

        Args:
            isin: ISIN облигации.
            date_from: Начало периода поиска (включительно) или ``None``.
            date_to: Конец периода поиска (включительно) или ``None``.

        Returns:
            HTML списка новостей по этой бумаге.

        """
        params = f"text={quote(isin)}"
        if date_from is not None:
            params += f"&from={date_from.strftime('%d.%m.%Y')}"
        if date_to is not None:
            params += f"&to={date_to.strftime('%d.%m.%Y')}"
        return await self._open(f"{_NEWS}?{params}")

    async def fetch_card(self, news_id: int) -> str:
        """Возвращает HTML карточки новости НРД.

        Args:
            news_id: Идентификатор новости (`/ru/news/view/<id>`).

        Returns:
            HTML карточки новости.

        """
        return await self._open(f"{_BASE}/ru/news/view/{news_id}")
