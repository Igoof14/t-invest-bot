"""Функции для работы с облигациями через T-Invest API."""

import asyncio
import heapq
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from features.users.repository import BotUserRepository
from t_tech.invest import AsyncClient
from t_tech.invest.schemas import (
    Bond,
    BondsResponse,
    GetAccountsResponse,
    OperationsResponse,
    OperationType,
    PortfolioResponse,
)

from ..moex.moex_bonds import MoexClient
from .common_func import to_float

logger = logging.getLogger(__name__)


@dataclass
class MaturityInfo:
    """Информация о погашении облигации."""

    name: str
    ticker: str
    maturity_date: datetime
    quantity: int
    nominal: float
    currency: str
    account_name: str


@dataclass
class OfferInfo:
    """Информация об оферте по облигации."""

    name: str
    ticker: str
    offer_date: datetime
    quantity: int
    nominal: float
    currency: str
    average_position_price: float
    moex_link: str


@dataclass
class CouponPaymentsByAccount:
    """Информация о платежах купонов по счётам."""

    total_amount: float = 0.0
    accounts: dict[str, float] = field(default_factory=dict)


async def get_nearest_maturities(telegram_id: int, limit: int = 5) -> list[MaturityInfo] | None:
    """Получает ближайшие погашения облигаций из портфеля пользователя.

    Args:
        telegram_id: ID пользователя в Telegram
        limit: Максимальное количество погашений для вывода

    Returns:
        Список MaturityInfo, отсортированный по дате погашения, или None если токен не найден

    """
    token = await BotUserRepository.get_token_by_telegram_id(telegram_id=telegram_id)
    if not token:
        return None

    bonds_with_maturity: list[MaturityInfo] = []

    async with AsyncClient(token) as client:
        all_bonds: BondsResponse = await client.instruments.bonds()
        bonds_cache = {bond.figi: bond for bond in all_bonds.instruments}

        accounts: GetAccountsResponse = await client.users.get_accounts()

        for account in accounts.accounts:
            portfolio: PortfolioResponse = await client.operations.get_portfolio(
                account_id=account.id
            )

            for position in portfolio.positions:
                if position.instrument_type != "bond":
                    continue

                bond = bonds_cache.get(position.figi)
                if not bond or not bond.maturity_date:
                    continue

                bonds_with_maturity.append(
                    MaturityInfo(
                        name=bond.name,
                        ticker=bond.ticker,
                        maturity_date=bond.maturity_date.replace(tzinfo=UTC),
                        quantity=int(to_float(position.quantity)),
                        nominal=to_float(bond.nominal),
                        currency=bond.currency,
                        account_name=account.name,
                    )
                )

    now = datetime.now(UTC)
    future_bonds = [b for b in bonds_with_maturity if b.maturity_date > now]
    future_bonds.sort(key=lambda x: x.maturity_date)
    return future_bonds[:limit]


async def get_nearest_offers(telegram_id: int, limit: int = 5) -> list[OfferInfo] | None:
    """Получает ближайшие оферты по облигациям из портфеля пользователя.

    Args:
        telegram_id: ID пользователя в Telegram
        limit: Максимальное количество оферт для вывода

    Returns:
        Список OfferInfo, отсортированный по дате оферты, или None если токен не найден

    """
    start_time: datetime = datetime.now(UTC)
    logger.info(f"Getting nearest offers for telegram_id={telegram_id}, start_time={start_time}")
    token = await BotUserRepository.get_token_by_telegram_id(telegram_id=telegram_id)
    if not token:
        logger.warning(f"Token not found for telegram_id={telegram_id}")
        return None

    async with AsyncClient(token) as tbank_client:
        accounts: GetAccountsResponse = await tbank_client.users.get_accounts()
        portfolios = await asyncio.gather(
            *[tbank_client.operations.get_portfolio(account_id=acc.id) for acc in accounts.accounts]
        )
        positions_by_ticker: dict[str, dict] = {}
        for portfolio in portfolios:
            for position in portfolio.positions:
                if position.instrument_type != "bond":
                    continue
                ticker = position.ticker
                qty = to_float(position.quantity)
                price = to_float(position.average_position_price)

                if ticker not in positions_by_ticker:
                    positions_by_ticker[ticker] = {
                        "quantity": 0.0,
                        "weighted_price_sum": 0.0,
                    }

                positions_by_ticker[ticker]["quantity"] += qty
                positions_by_ticker[ticker]["weighted_price_sum"] += qty * price

        logger.info(f"Found {len(positions_by_ticker)} unique bonds to check for offers")

        async with MoexClient(concurrency_limit=10) as moex_client:
            offers_by_ticker = await moex_client.get_many_next_bond_offers(
                isins=list(positions_by_ticker.keys()),
            )
        offers_dict: dict[str, OfferInfo] = {}

        for ticker, position in positions_by_ticker.items():
            offer = offers_by_ticker.get(ticker)
            if offer is None:
                continue
            try:
                offer_date = datetime.combine(
                    offer.offerdate,
                    datetime.min.time(),
                    tzinfo=UTC,
                )

                average_position_price = (
                    position["weighted_price_sum"] / position["quantity"]
                    if position["quantity"]
                    else 0.0
                )

                offers_dict[ticker] = OfferInfo(
                    name=offer.name,
                    ticker=ticker,
                    offer_date=offer_date,
                    quantity=position["quantity"],
                    nominal=offer.facevalue,
                    currency=offer.faceunit,
                    average_position_price=average_position_price,
                    moex_link=f"https://www.moex.com/ru/issue.aspx?board={offer.primary_boardid}&code={ticker}",
                )

            except Exception as e:
                logger.error(f"Error processing name={offer.name}, ticker={ticker}: {e}")

        end_time = datetime.now(UTC)

        logger.info(f"End time: {end_time}")
        logger.info(f"Time taken: {end_time - start_time}")

        return heapq.nsmallest(
            limit,
            offers_dict.values(),
            key=lambda x: x.offer_date,
        )


async def get_coupon_payment(
    telegram_id: int, start_datetime: datetime
) -> CouponPaymentsByAccount | None:
    """Получает сумму выплат купонов за период.

    Args:
        telegram_id: Telegram ID пользователя
        start_datetime: Начало периода

    Returns:
        Отформатированное сообщение с суммами выплат

    """
    token = await BotUserRepository.get_token_by_telegram_id(telegram_id=telegram_id)
    if not token:
        logger.warning(f"Token not found for telegram_id={telegram_id}")
        return None

    async with AsyncClient(token) as client:
        accounts: GetAccountsResponse = await client.users.get_accounts()

        response: CouponPaymentsByAccount = CouponPaymentsByAccount()
        total_portfolio_amount = 0.0

        for account in accounts.accounts:
            operations: OperationsResponse = await client.operations.get_operations(
                account_id=account.id,
                from_=start_datetime,
            )

            account_amount: float = 0.0
            for operation in operations.operations:
                if operation.operation_type == OperationType.OPERATION_TYPE_COUPON:
                    operation_amount: float = to_float(operation.payment)
                    account_amount += operation_amount

            response.accounts[account.name] = account_amount
            total_portfolio_amount += account_amount

        response.total_amount = total_portfolio_amount
    return response
