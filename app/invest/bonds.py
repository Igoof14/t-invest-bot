"""Функции для работы с облигациями через T-Invest API."""

import logging
from datetime import UTC, datetime, timedelta

from storage import BotUserStorage

from .models import EventType
from .tbank_client import TBankClient

logger = logging.getLogger(__name__)


async def get_nearest_maturities(telegram_id: int, limit: int = 5) -> str | None:
    """Получает ближайшие погашения облигаций из портфеля пользователя.

    Args:
        telegram_id: ID пользователя в Telegram
        limit: Максимальное количество погашений для вывода

    Returns:
        Отформатированное сообщение со списком погашений

    """
    token = await BotUserStorage.get_token_by_telegram_id(telegram_id=telegram_id)
    if not token:
        return "Токен не найден. Добавьте токен в настройках."

    bonds_with_maturity: list[dict] = []

    async with TBankClient(token) as client:
        # Получаем все облигации одним запросом и строим кэш по figi
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

                quantity = int(position.quantity.to_float())
                current_price = position.current_price.to_float()
                nominal = bond.nominal.to_float()

                bonds_with_maturity.append(
                    {
                        "name": bond.name,
                        "ticker": bond.ticker,
                        "maturity_date": bond.maturity_date,
                        "quantity": quantity,
                        "nominal": nominal,
                        "current_price": current_price,
                        "currency": bond.currency,
                        "account_name": account.name,
                    }
                )

    if not bonds_with_maturity:
        return None

    now = datetime.now(UTC)
    future_bonds = [b for b in bonds_with_maturity if b["maturity_date"] > now]
    future_bonds.sort(key=lambda x: x["maturity_date"])
    nearest = future_bonds[:limit]

    if not nearest:
        return "Нет облигаций с будущими датами погашения."

    message_lines = []
    for i, bond in enumerate(nearest, 1):
        maturity_str = bond["maturity_date"].strftime("%d.%m.%Y")
        days_left = (bond["maturity_date"] - now).days
        total_nominal = bond["nominal"] * bond["quantity"]

        line = (
            f"{i}. <code>{bond['ticker']}</code>\n"
            f"   {bond['name']}\n"
            f"   Погашение: {maturity_str} ({days_left} дн.)\n"
            f"   Кол-во: {bond['quantity']} шт. x {bond['nominal']:.0f} = "
            f"{total_nominal:,.0f} {bond['currency'].upper()}\n"
            f"   Счёт: {bond['account_name']}\n"
        )
        message_lines.append(line)

    return "\n".join(message_lines)


async def get_nearest_offers(telegram_id: int, limit: int = 5) -> str | None:
    """Получает ближайшие оферты по облигациям из портфеля пользователя.

    Args:
        telegram_id: ID пользователя в Telegram
        limit: Максимальное количество оферт для вывода

    Returns:
        Отформатированное сообщение со списком оферт

    """
    logger.info(f"Getting nearest offers for telegram_id={telegram_id}")
    token = await BotUserStorage.get_token_by_telegram_id(telegram_id=telegram_id)
    if not token:
        logger.warning(f"Token not found for telegram_id={telegram_id}")
        return "Токен не найден. Добавьте токен в настройках."

    now = datetime.now(UTC)
    future_date = now + timedelta(days=365)
    logger.info(f"Searching offers from {now.isoformat()} to {future_date.isoformat()}")

    async with TBankClient(token) as client:
        # 1. Получаем все облигации одним запросом и строим кэш по figi
        all_bonds = await client.get_bonds()
        bonds_cache = {bond.figi: bond for bond in all_bonds}

        # 2. Собираем позиции из портфелей
        positions_by_figi: dict[str, list[dict]] = {}  # figi -> [{account_name, quantity}]
        accounts = await client.get_accounts()

        for account in accounts:
            portfolio = await client.get_portfolio(account_id=account.id)

            for position in portfolio.positions:
                if position.instrument_type != "bond":
                    continue

                figi = position.figi
                if figi not in positions_by_figi:
                    positions_by_figi[figi] = []

                positions_by_figi[figi].append({
                    "account_name": account.name,
                    "quantity": int(position.quantity.to_float()),
                })

        # 3. Запрашиваем события только для уникальных figi
        logger.info(f"Found {len(positions_by_figi)} unique bonds to check for offers")
        offers_dict: dict[tuple, dict] = {}  # ключ: (ticker, offer_date, account_name)

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
                    nominal = bond.nominal.to_float()

                    # Добавляем запись для каждого счёта, где есть эта облигация
                    for pos in positions:
                        key = (bond.ticker, event.event_date, pos["account_name"])
                        if key not in offers_dict:
                            offers_dict[key] = {
                                "name": bond.name,
                                "ticker": bond.ticker,
                                "offer_date": event.event_date,
                                "quantity": pos["quantity"],
                                "nominal": nominal,
                                "currency": bond.currency,
                                "account_name": pos["account_name"],
                            }
            except Exception as e:
                logger.error(f"Error getting bond events for figi={figi}, ticker={bond.ticker}: {e}")
                continue

    if not offers_dict:
        logger.info("No offers found for the next year")
        return None

    offers_list = sorted(offers_dict.values(), key=lambda x: x["offer_date"])
    nearest = offers_list[:limit]

    message_lines = []
    for i, offer in enumerate(nearest, 1):
        offer_str = offer["offer_date"].strftime("%d.%m.%Y")
        days_left = (offer["offer_date"] - now).days
        total_nominal = offer["nominal"] * offer["quantity"]

        line = (
            f"{i}. <code>{offer['ticker']}</code>\n"
            f"   {offer['name']}\n"
            f"   Оферта: {offer_str} ({days_left} дн.)\n"
            f"   Кол-во: {offer['quantity']} шт. x {offer['nominal']:.0f} = "
            f"{total_nominal:,.0f} {offer['currency'].upper()}\n"
            f"   Счёт: {offer['account_name']}\n"
        )
        message_lines.append(line)

    return "\n".join(message_lines)
