"""Получение облигаций из портфеля пользователя через T-Invest API."""

from __future__ import annotations

import logging

from t_tech.invest import AsyncClient

logger = logging.getLogger(__name__)


async def get_portfolio_bond_isins(token: str, telegram_id: int | None = None) -> list[str]:
    """Возвращает уникальные тикеры облигаций из всех счетов пользователя.

    Тикер используется как идентификатор при запросе оферт через MOEX ISS API.

    Args:
        token: T-Invest API токен пользователя.
        telegram_id: Telegram ID для логов.

    Returns:
        Список тикеров. Пустой при ошибке или отсутствии облигаций.

    """
    user_label = f" пользователя {telegram_id}" if telegram_id is not None else ""
    seen: set[str] = set()

    try:
        async with AsyncClient(token) as client:
            accounts = await client.users.get_accounts()

            for account in accounts.accounts:
                try:
                    portfolio = await client.operations.get_portfolio(account_id=account.id)

                    for position in portfolio.positions:
                        if position.instrument_type != "bond":
                            continue
                        if position.ticker:
                            seen.add(position.ticker)

                except Exception as e:
                    logger.error(
                        f"Ошибка при получении портфеля счёта {account.id}{user_label}: {e}"
                    )

    except Exception as e:
        logger.error(f"Ошибка при получении облигаций{user_label}: {e}")

    return list(seen)
