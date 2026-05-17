"""Функции для работы с облигациями через T-Invest API."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from storage import BotUserStorage, PriceAlertStorage

from .models import Bond, EventType, OperationType
from .tbank_client import TBankClient

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
    account_name: str


async def fetch_bonds_cache() -> dict[str, Bond]:
    """Загружает все облигации с биржи и возвращает словарь figi -> Bond.

    Вызывается один раз за цикл проверки, результат передаётся в get_portfolio_bond_prices.


    ТУТ НУЖНО БУДЕТ ПОМЕНЯТЬ ЛОГИКУ ПОЛУЧЕНИЯ ТОКЕНА
    """
    try:
        # Используем любой валидный токен для получения справочника
        users_with_alerts = await AlertStorage.get_all_users_with_alerts_enabled()
        for telegram_id in users_with_alerts:
            token = await BotUserStorage.get_token_by_telegram_id(telegram_id=telegram_id)
            if token:
                async with TBankClient(token) as client:
                    all_bonds = await client.get_bonds()
                    return {bond.figi: bond for bond in all_bonds}
    except Exception as e:
        logger.error(f"Ошибка при загрузке справочника облигаций: {e}")

    return {}


async def get_nearest_maturities(telegram_id: int, limit: int = 5) -> list[MaturityInfo] | None:
    """Получает ближайшие погашения облигаций из портфеля пользователя.

    Args:
        telegram_id: ID пользователя в Telegram
        limit: Максимальное количество погашений для вывода

    Returns:
        Список MaturityInfo, отсортированный по дате погашения, или None если токен не найден

    """
    token = await BotUserStorage.get_token_by_telegram_id(telegram_id=telegram_id)
    if not token:
        return None

    bonds_with_maturity: list[MaturityInfo] = []

    async with TBankClient(token) as client:
        all_bonds = await client.get_bonds()
        bonds_cache = {bond.figi: bond for bond in all_bonds}

        accounts = await client.get_accounts()

        for account in accounts:
            portfolio = await client.get_portfolio(account_id=account.id)

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
                        quantity=int(position.quantity.to_float()),
                        nominal=bond.nominal.to_float(),
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
    logger.info(f"Getting nearest offers for telegram_id={telegram_id}")
    token = await BotUserStorage.get_token_by_telegram_id(telegram_id=telegram_id)
    if not token:
        logger.warning(f"Token not found for telegram_id={telegram_id}")
        return None

    now = datetime.now(UTC)
    future_date = now + timedelta(days=365)
    logger.info(f"Searching offers from {now.isoformat()} to {future_date.isoformat()}")

    async with TBankClient(token) as client:
        all_bonds = await client.get_bonds()
        bonds_cache = {bond.figi: bond for bond in all_bonds}

        positions_by_figi: dict[str, list[dict]] = {}
        accounts = await client.get_accounts()

        for account in accounts:
            portfolio = await client.get_portfolio(account_id=account.id)

            for position in portfolio.positions:
                if position.instrument_type != "bond":
                    continue

                figi = position.figi
                positions_by_figi.setdefault(figi, []).append(
                    {
                        "account_name": account.name,
                        "quantity": int(position.quantity.to_float()),
                    }
                )

        logger.info(f"Found {len(positions_by_figi)} unique bonds to check for offers")
        offers_dict: dict[tuple, OfferInfo] = {}

        for figi, positions in positions_by_figi.items():
            bond = bonds_cache.get(figi)
            if not bond:
                continue

            try:
                logger.debug(
                    f"Requesting bond events for figi={figi}, ticker={bond.ticker}, "
                    f"from={now.isoformat()}, to={future_date.isoformat()}"
                )
                events = await client.get_bond_events(
                    instrument_id=figi,
                    from_=now,
                    to=future_date,
                    event_type=EventType.EVENT_TYPE_CALL,
                )
                logger.debug(f"Got {len(events)} events for {bond.ticker}")

                for event in events:
                    for pos in positions:
                        key = (bond.ticker, event.event_date, pos["account_name"])
                        if key not in offers_dict:
                            offers_dict[key] = OfferInfo(
                                name=bond.name,
                                ticker=bond.ticker,
                                offer_date=event.event_date.replace(tzinfo=UTC),
                                quantity=pos["quantity"],
                                nominal=bond.nominal.to_float(),
                                currency=bond.currency,
                                account_name=pos["account_name"],
                            )
            except Exception as e:
                logger.error(
                    f"Error getting bond events for figi={figi}, ticker={bond.ticker}: {e}"
                )
                continue

            await asyncio.sleep(0.05)

    return sorted(offers_dict.values(), key=lambda x: x.offer_date)[:limit]


async def get_coupon_payment(user_id: int, start_datetime: datetime) -> str:
    """Получает сумму выплат купонов за период.

    Args:
        user_id: Telegram ID пользователя
        start_datetime: Начало периода

    Returns:
        Отформатированное сообщение с суммами выплат

    """
    token = await BotUserStorage.get_token_by_telegram_id(telegram_id=user_id)
    if not token:
        return "Токен не найден. Добавьте токен в настройках."

    async with TBankClient(token) as client:
        accounts = await client.get_accounts()

        total_amount = 0.0
        message = ""

        for account in accounts:
            operations = await client.get_operations(
                account_id=account.id,
                from_=start_datetime,
            )

            account_amount = 0.0
            if not operations:
                message += f"<b>{account.name}</b>: 0₽\n"
                continue

            for operation in operations:
                if operation.operation_type == OperationType.OPERATION_TYPE_COUPON.value:
                    operation_amount = operation.payment.to_float()
                    account_amount += operation_amount

            total_amount += account_amount
            message += f"<b>{account.name}</b>: {account_amount:,.2f}₽\n"

        message += f"\n<b>Сумма выплат:</b> {total_amount:,.2f}₽"

        return message
