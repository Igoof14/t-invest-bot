"""Получение идентификаторов облигаций из портфеля через T-Invest API."""

from __future__ import annotations

import logging

from t_tech.invest import AsyncClient

logger = logging.getLogger(__name__)


async def get_portfolio_bond_identifiers(
    token: str, telegram_id: int | None = None
) -> set[str]:
    """Возвращает идентификаторы облигаций из всех счетов пользователя.

    Собирает ``figi`` и ``ticker`` каждой облигационной позиции — этого
    достаточно, чтобы сопоставить позиции с облигациями эмитента (у которых
    известны figi/ticker/isin) по пересечению множеств.

    Args:
        token: T-Invest API токен пользователя.
        telegram_id: Telegram ID для логов.

    Returns:
        Множество идентификаторов. Пустое при ошибке или отсутствии облигаций.

    """
    user_label = f" пользователя {telegram_id}" if telegram_id is not None else ""
    identifiers: set[str] = set()

    try:
        async with AsyncClient(token) as client:
            accounts = await client.users.get_accounts()

            for account in accounts.accounts:
                try:
                    portfolio = await client.operations.get_portfolio(account_id=account.id)

                    for position in portfolio.positions:
                        if position.instrument_type != "bond":
                            continue
                        if position.figi:
                            identifiers.add(position.figi)
                        if position.ticker:
                            identifiers.add(position.ticker)

                except Exception as e:
                    logger.error(
                        f"Ошибка при получении портфеля счёта {account.id}{user_label}: {e}"
                    )

    except Exception as e:
        logger.error(f"Ошибка при получении облигаций{user_label}: {e}")

    return identifiers
