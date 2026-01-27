"""REST клиент для T-Invest API."""

import logging
from datetime import datetime
from typing import Any

import aiohttp

from .models import (
    Bond,
    BondEvent,
    BondsResponse,
    EventType,
    GetAccountsResponse,
    GetBondEventsResponse,
    GetOperationsResponse,
    GetPortfolioResponse,
    Operation,
    PortfolioPosition,
    UserInfo,
    Account,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://invest-public-api.tinkoff.ru/rest"


class TBankAPIError(Exception):
    """Ошибка API T-Invest."""

    def __init__(self, message: str, code: str = ""):
        self.message = message
        self.code = code
        super().__init__(f"{code}: {message}" if code else message)


class TBankClient:
    """Асинхронный REST клиент для T-Invest API."""

    def __init__(self, token: str):
        """Инициализация клиента.

        Args:
            token: API токен T-Invest

        """
        self.token = token
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> "TBankClient":
        """Вход в контекстный менеджер."""
        self._session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Выход из контекстного менеджера."""
        if self._session:
            await self._session.close()
            self._session = None

    async def _request(self, endpoint: str, data: dict | None = None) -> dict[str, Any]:
        """Выполняет POST запрос к API.

        Args:
            endpoint: Путь endpoint (без base URL)
            data: Тело запроса

        Returns:
            JSON ответ

        Raises:
            TBankAPIError: При ошибке API

        """
        if not self._session:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        url = f"{BASE_URL}/{endpoint}"
        payload = data or {}

        try:
            async with self._session.post(url, json=payload) as response:
                result = await response.json()

                if response.status != 200:
                    error_msg = result.get("message", "Unknown error")
                    error_code = result.get("code", "")
                    logger.error(f"API error: {error_code} - {error_msg}")
                    raise TBankAPIError(error_msg, error_code)

                return result

        except aiohttp.ClientError as e:
            logger.error(f"HTTP error: {e}")
            raise TBankAPIError(f"HTTP error: {e}")

    # === UsersService ===

    async def get_accounts(self) -> list[Account]:
        """Получает список счетов пользователя."""
        endpoint = "tinkoff.public.invest.api.contract.v1.UsersService/GetAccounts"
        result = await self._request(endpoint)
        response = GetAccountsResponse(**result)
        return response.accounts

    async def get_info(self) -> UserInfo:
        """Получает информацию о пользователе."""
        endpoint = "tinkoff.public.invest.api.contract.v1.UsersService/GetInfo"
        result = await self._request(endpoint)
        return UserInfo(**result)

    # === OperationsService ===

    async def get_operations(
        self,
        account_id: str,
        from_: datetime,
        to: datetime | None = None,
    ) -> list[Operation]:
        """Получает список операций по счёту.

        Args:
            account_id: ID счёта
            from_: Начало периода
            to: Конец периода (по умолчанию — сейчас)

        """
        endpoint = "tinkoff.public.invest.api.contract.v1.OperationsService/GetOperations"

        if to is None:
            to = datetime.utcnow()

        data = {
            "accountId": account_id,
            "from": from_.isoformat() + "Z",
            "to": to.isoformat() + "Z",
        }

        result = await self._request(endpoint, data)
        response = GetOperationsResponse(**result)
        return response.operations

    async def get_portfolio(self, account_id: str) -> GetPortfolioResponse:
        """Получает портфель по счёту.

        Args:
            account_id: ID счёта

        """
        endpoint = "tinkoff.public.invest.api.contract.v1.OperationsService/GetPortfolio"
        data = {"accountId": account_id}
        result = await self._request(endpoint, data)
        return GetPortfolioResponse(**result)

    # === InstrumentsService ===

    async def get_bonds(self, instrument_status: str = "INSTRUMENT_STATUS_BASE") -> list[Bond]:
        """Получает список всех облигаций.

        Args:
            instrument_status: Статус инструментов

        """
        endpoint = "tinkoff.public.invest.api.contract.v1.InstrumentsService/Bonds"
        data = {"instrumentStatus": instrument_status}
        result = await self._request(endpoint, data)
        response = BondsResponse(**result)
        return response.instruments

    async def get_bond_events(
        self,
        instrument_id: str,
        from_: datetime,
        to: datetime,
        event_type: EventType = EventType.EVENT_TYPE_CALL,
    ) -> list[BondEvent]:
        """Получает события по облигации.

        Args:
            instrument_id: FIGI облигации
            from_: Начало периода
            to: Конец периода
            event_type: Тип события

        """
        endpoint = "tinkoff.public.invest.api.contract.v1.InstrumentsService/GetBondEvents"
        data = {
            "instrumentId": instrument_id,
            "from": from_.isoformat() + "Z",
            "to": to.isoformat() + "Z",
            "type": event_type.value,
        }

        result = await self._request(endpoint, data)
        response = GetBondEventsResponse(**result)
        return response.events


# Синхронная обёртка для проверки токена
def check_token_sync(token: str) -> bool:
    """Синхронная проверка токена (для совместимости)."""
    import asyncio

    async def _check():
        try:
            async with TBankClient(token) as client:
                await client.get_info()
            return True
        except Exception as e:
            logger.error(f"Ошибка проверки токена: {e}")
            return False

    return asyncio.run(_check())
