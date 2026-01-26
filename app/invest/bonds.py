from datetime import UTC, datetime, timedelta

from storage import BotUserStorage
from tinkoff.invest import Client
from tinkoff.invest.schemas import EventType, GetBondEventsRequest


async def get_bonds(telegram_id: int):
    """Получает список облигаций пользователя."""
    token = await BotUserStorage.get_token_by_telegram_id(telegram_id=telegram_id)
    if not token:
        return []

    with Client(token) as client:
        bonds = client.instruments.get_bond_events()
        return bonds.instruments


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

    with Client(token) as client:
        # Получаем все облигации одним запросом и строим кэш по figi
        all_bonds = client.instruments.bonds()
        bonds_cache = {bond.figi: bond for bond in all_bonds.instruments}

        accounts = client.users.get_accounts()

        for account in accounts.accounts:
            portfolio = client.operations.get_portfolio(account_id=account.id)

            for position in portfolio.positions:
                if position.instrument_type != "bond":
                    continue

                bond = bonds_cache.get(position.figi)
                if not bond or not bond.maturity_date:
                    continue

                quantity = int(position.quantity.units)
                current_price = (
                    position.current_price.units + position.current_price.nano / 1e9
                )
                nominal = bond.nominal.units + bond.nominal.nano / 1e9

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
    token = await BotUserStorage.get_token_by_telegram_id(telegram_id=telegram_id)
    if not token:
        return "Токен не найден. Добавьте токен в настройках."

    now = datetime.now(UTC)
    future_date = now + timedelta(days=365 * 5)

    with Client(token) as client:
        # 1. Получаем все облигации одним запросом и строим кэш по figi
        all_bonds = client.instruments.bonds()
        bonds_cache = {bond.figi: bond for bond in all_bonds.instruments}

        # 2. Собираем позиции из портфелей
        positions_by_figi: dict[str, list[dict]] = {}  # figi -> [{account_name, quantity}]
        accounts = client.users.get_accounts()

        for account in accounts.accounts:
            portfolio = client.operations.get_portfolio(account_id=account.id)

            for position in portfolio.positions:
                if position.instrument_type != "bond":
                    continue

                figi = position.figi
                if figi not in positions_by_figi:
                    positions_by_figi[figi] = []

                positions_by_figi[figi].append({
                    "account_name": account.name,
                    "quantity": int(position.quantity.units),
                })

        # 3. Запрашиваем события только для уникальных figi
        offers_dict: dict[tuple, dict] = {}  # ключ: (ticker, offer_date, account_name)

        for figi, positions in positions_by_figi.items():
            bond = bonds_cache.get(figi)
            if not bond:
                continue

            try:
                events = client.instruments.get_bond_events(
                    request=GetBondEventsRequest(
                        instrument_id=figi,
                        from_=now,
                        to=future_date,
                        type=EventType.EVENT_TYPE_CALL,
                    )
                )

                for event in events.events:
                    nominal = bond.nominal.units + bond.nominal.nano / 1e9

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
            except Exception:
                continue

    if not offers_dict:
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
