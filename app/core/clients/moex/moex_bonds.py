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


# from pprint import pprint


# async def main():
#     isins = ["RU000A10B2J9", "RU000A106EM8", "RU000A10BGY3", "RU000A105RV3"]

#     async with MoexClient(
#         concurrency_limit=5,
#     ) as client:
#         offers = await client.get_many_next_bond_offers(isins)

#         for isin, offer in offers.items():
#             print()
#             pprint(offer)

#         print(offers)


# asyncio.run(main())
