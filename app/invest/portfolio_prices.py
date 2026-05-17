"""Получение текущих цен облигаций из портфеля пользователя через T-Invest API."""

import logging
from dataclasses import dataclass

from .models import Bond
from .tbank_client import TBankClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class BondPrice:
    """Снимок цены облигации в портфеле пользователя."""

    figi: str
    ticker: str
    name: str
    price: float
    account_name: str


async def fetch_portfolio_bond_prices(
    token: str,
    bonds_cache: dict[str, Bond],
    *,
    telegram_id: int | None = None,
) -> list[BondPrice]:
    """Получает цены облигаций по всем счетам пользователя.

    Args:
        token: Токен T-Invest API пользователя.
        bonds_cache: Кэш облигаций (figi -> Bond), общий для всех пользователей.
        telegram_id: ID пользователя в Telegram. Используется только в логах.

    Returns:
        Список BondPrice. Пустой при ошибках или отсутствии облигаций.

    """
    bond_prices: list[BondPrice] = []

    try:
        async with TBankClient(token) as client:
            accounts = await client.get_accounts()

            for account in accounts:
                try:
                    portfolio = await client.get_portfolio(account_id=account.id)

                    for position in portfolio.positions:
                        if position.instrument_type != "bond":
                            continue

                        bond = bonds_cache.get(position.figi)
                        if not bond:
                            continue

                        # Цена в процентах от номинала
                        current_price = position.current_price.to_float()

                        bond_prices.append(
                            BondPrice(
                                figi=position.figi,
                                ticker=bond.ticker,
                                name=bond.name,
                                price=current_price,
                                account_name=account.name,
                            )
                        )

                except Exception as e:
                    logger.error(f"Ошибка при получении портфеля счёта {account.id}: {e}")
                    continue

    except Exception as e:
        user_part = f" для пользователя {telegram_id}" if telegram_id is not None else ""
        logger.error(f"Ошибка при получении цен облигаций{user_part}: {e}")

    return bond_prices
