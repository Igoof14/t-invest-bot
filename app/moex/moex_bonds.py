# """Модуль для работы облигациями через API Московской биржи."""

# import asyncio
# from datetime import date

# import aiohttp


# class MoexClient:
#     """Клиент для работы с API Московской биржи."""

#     BASE_URL = "https://iss.moex.com/iss"

#     def __init__(self):
#         """Инициализация клиента."""
#         self._session: aiohttp.ClientSession | None = None

#     async def __aenter__(self):
#         """Асинхронный вход в контекст."""
#         self._session = aiohttp.ClientSession()
#         return self

#     async def __aexit__(self, *args):
#         """Асинхронный выход из контекста."""
#         if self._session:
#             await self._session.close()

#     async def get_next_bond_offer(self, isin: str) -> dict | None:
#         """Получение информации о следующей оферте(пут) пол облигации."""
#         if self._session is None:
#             raise RuntimeError("Клиент не инициализирован. Используйте 'async with MoexClient()'")

#         url = f"{self.BASE_URL}/securities/{isin}/bondization.json"

#         async with self._session.get(url) as response:
#             data = await response.json()

#         offers = data.get("offers", {})
#         columns = offers.get("columns", [])
#         rows = offers.get("data", [])

#         all_offers = [dict(zip(columns, row, strict=False)) for row in rows]

#         today = date.today()
#         future_offers = [
#             o
#             for o in all_offers
#             if o.get("offerdate") and date.fromisoformat(o["offerdate"]) >= today
#         ]

#         if not future_offers:
#             return None

#         return min(future_offers, key=lambda o: date.fromisoformat(o["offerdate"]))


# async def main():
#     """Пример использования клиента для получения следующей оферты облигации."""
#     async with MoexClient() as client:
#         offer = await client.get_next_bond_offer("RU000A106EM8")
#         print(offer)


# asyncio.run(main())

import asyncio
from datetime import date
from typing import Any

import aiohttp
from pydantic import BaseModel


class MoexBondOffer(BaseModel):
    isin: str
    name: str

    issuevalue: int | None = None

    offerdate: date
    offerdatestart: date | None = None
    offerdateend: date | None = None

    facevalue: float | None = None
    faceunit: str | None = None

    price: float | None = None
    value: float | None = None

    agent: str | None = None
    offertype: str | None = None

    secid: str
    primary_boardid: str | None = None


class MoexClient:
    BASE_URL = "https://iss.moex.com/iss"

    def __init__(
        self,
        concurrency_limit: int = 10,
        timeout: int = 10,
    ):
        self._session: aiohttp.ClientSession | None = None
        self._semaphore = asyncio.Semaphore(concurrency_limit)
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    async def __aenter__(self):
        self._session = aiohttp.ClientSession(
            timeout=self._timeout,
        )
        return self

    async def __aexit__(self, *args):
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
            if isinstance(result, Exception):
                print(f"Error for {isin}: {result}")
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
