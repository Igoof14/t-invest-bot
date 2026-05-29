# import logging

# from t_tech.invest import AsyncClient
# from t_tech.invest.schemas import Bond, GetLastPricesResponse

# logger = logging.getLogger(__name__)


# async def fetch_bonds_cache() -> dict[str, Bond]:
#     """Загружает все облигации с биржи и возвращает словарь figi -> Bond.

#     Вызывается один раз за цикл проверки, результат передаётся в get_portfolio_bond_prices.
#     """
#     token = (
#         "t.o0IQmaErTEIlLxBYGOqZ3RtmAwZDeYAy5RNAv9rpSCH1SQN4kv4LmW7t48ufuczb7xMPnjV3DEamt5ZOcu36XA"
#     )

#     try:
#         async with AsyncClient(token) as client:
#             all_bonds = await client.instruments.bonds()
#             return {bond.figi: bond for bond in all_bonds.instruments}
#     except Exception as e:
#         logger.warning(f"Не удалось загрузить облигации: {e}")
#         return {}


# async def fetch_instrumetns_last_price(figis: list[str]) -> GetLastPricesResponse | None:
#     """Asdfgas."""
#     import os

#     token = (
#         "t.o0IQmaErTEIlLxBYGOqZ3RtmAwZDeYAy5RNAv9rpSCH1SQN4kv4LmW7t48ufuczb7xMPnjV3DEamt5ZOcu36XA"
#     )
#     if not token:
#         logger.warning("Токен не найден")
#         return None
#     try:
#         async with AsyncClient(token) as client:
#             last_prices: GetLastPricesResponse = await client.market_data.get_last_prices(figi=figis)
#             return last_price
#     except Exception as e:
#         logger.warning(f"Не удалось загрузить облигации через пользователя : {e}")

#     return None


# import asyncio


# async def main():
#     bonds = await fetch_bonds_cache()
#     figis = list(bonds.keys())
#     print(figis)

#     last_prices = await fetch_instrumetns_last_price(figis)
#     print(last_prices)


# asyncio.run(main())
