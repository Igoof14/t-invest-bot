"""Модуль для работы облигациями через API Московской биржи."""

import asyncio
import logging
from datetime import date
from typing import Any

import aiohttp
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class MoexBondOffer(BaseModel):
    """Данные о следующей оферте облигации по данным MOEX."""

    isin: str
    name: str

    issuevalue: int | None = None

    offerdate: date
    offerdatestart: date | None = None
    offerdateend: date | None = None

    facevalue: float
    faceunit: str

    price: float | None = None
    value: float | None = None

    agent: str | None = None
    offertype: str | None = None

    secid: str
    primary_boardid: str | None = None


class MoexEmitter(BaseModel):
    """Данные об эмитенте облигации по данным MOEX ISS."""

    emitter_id: int
    inn: str | None = None
    title: str | None = None
    short_title: str | None = None
    ogrn: str | None = None
    okpo: str | None = None
    legal_address: str | None = None
    url: str | None = None

    # ISIN/secid, по которому эмитент был найден
    secid: str


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
    def _parse_offers(
        data: dict[str, Any],
    ) -> list[MoexBondOffer]:
        offers = data.get("offers", {})
        columns = offers.get("columns", [])
        rows = offers.get("data", [])

        parsed_offers: list[MoexBondOffer] = []

        for row in rows:
            raw_offer = dict(zip(columns, row, strict=False))

            if not raw_offer.get("offerdate"):
                continue

            parsed_offers.append(MoexBondOffer.model_validate(raw_offer))

        return parsed_offers

    async def get_next_bond_offer(
        self,
        isin: str,
    ) -> MoexBondOffer | None:
        """Получение следующей оферты облигации по ISIN."""
        data = await self._request_json(f"/securities/{isin}/bondization.json")

        offers = self._parse_offers(data)

        today = date.today()

        future_offers = [offer for offer in offers if offer.offerdate >= today]

        if not future_offers:
            return None

        return min(
            future_offers,
            key=lambda offer: offer.offerdate,
        )

    async def get_many_next_bond_offers(
        self,
        isins: list[str],
    ) -> dict[str, MoexBondOffer | None]:
        """Получение следующих оферт облигаций по списку ISIN."""
        tasks = [self.get_next_bond_offer(isin) for isin in isins]

        results = await asyncio.gather(
            *tasks,
            return_exceptions=True,
        )

        offers: dict[str, MoexBondOffer | None] = {}

        for isin, result in zip(
            isins,
            results,
            strict=False,
        ):
            if isinstance(result, BaseException):
                logger.error(f"Error for {isin}: {result}")
                offers[isin] = None

            else:
                offers[isin] = result

        return offers

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

    async def get_emitter(self, emitter_id: int, secid: str) -> MoexEmitter | None:
        """Возвращает данные эмитента по его MOEX ``EMITTER_ID``."""
        data = await self._request_json(f"/emitters/{emitter_id}.json?iss.meta=off")
        emitter_block = data.get("emitter", {})
        columns = emitter_block.get("columns", [])
        rows = emitter_block.get("data", [])
        if not rows:
            return None

        raw = dict(zip(columns, rows[0], strict=False))

        def _str(value: Any) -> str | None:
            return str(value) if value is not None else None

        return MoexEmitter(
            emitter_id=emitter_id,
            inn=_str(raw.get("INN")),
            title=raw.get("TITLE"),
            short_title=raw.get("SHORT_TITLE"),
            ogrn=_str(raw.get("OGRN")),
            okpo=_str(raw.get("OKPO")),
            legal_address=raw.get("LEGAL_ADDRESS"),
            url=raw.get("URL"),
            secid=secid.upper(),
        )

    async def get_issuer_by_secid(
        self, secid: str, emitter_cache: dict[int, MoexEmitter]
    ) -> MoexEmitter | None:
        """Возвращает эмитента бумаги по ISIN/secid (двухшаговый запрос).

        Сначала по бумаге ищется ``EMITTER_ID``, затем по нему — данные эмитента.
        Эмитенты кэшируются: у одной компании может быть много облигаций
        (например, у РЖД), и повторный запрос для известного ``emitter_id`` не
        выполняется.
        """
        emitter_id, _ = await self._get_emitter_id(secid)
        if emitter_id is None:
            return None

        cached = emitter_cache.get(emitter_id)
        if cached is not None:
            # Возвращаем копию с актуальным secid, по которому нашли.
            return cached.model_copy(update={"secid": secid.upper()})

        emitter = await self.get_emitter(emitter_id, secid)
        if emitter is not None:
            emitter_cache[emitter_id] = emitter
        return emitter

    async def get_many_issuers(self, secids: list[str]) -> dict[str, MoexEmitter | None]:
        """Возвращает эмитентов для списка ISIN/secid, запрашивая их конкурентно.

        Args:
            secids: Список ISIN/secid облигаций.

        Returns:
            Словарь ``secid -> MoexEmitter | None``. ``None`` — если эмитент не
            найден или произошла ошибка запроса.

        """
        emitter_cache: dict[int, MoexEmitter] = {}
        tasks = [self.get_issuer_by_secid(secid, emitter_cache) for secid in secids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        issuers: dict[str, MoexEmitter | None] = {}
        for secid, result in zip(secids, results, strict=False):
            if isinstance(result, BaseException):
                logger.error(f"Error fetching issuer for {secid}: {result}")
                issuers[secid] = None
            else:
                issuers[secid] = result

        return issuers
