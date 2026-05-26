"""Модуль для взаимодействия с API T-Invest в рамкам фичи мониторига цен."""

import logging

from core.clients.t_invest.common_func import to_float
from t_tech.invest import AsyncClient
from t_tech.invest.schemas import Bond

from ..users.repository import BotUserRepository
from .repository import AlertSettingsRepository
from .schemas import BondPrice

logger = logging.getLogger(__name__)


async def get_bonds() -> dict[str, Bond] | None:
    """Загружает все облигации с биржи и возвращает словарь figi -> Bond.

    Вызывается один раз за цикл проверки, результат передаётся в get_portfolio_bond_prices.
    """
    users_settings = await AlertSettingsRepository.list_users_with_alerts_enabled()
    for settings in users_settings:
        token = await BotUserRepository.get_token_by_telegram_id(telegram_id=settings.telegram_id)
        if not token:
            continue
        try:
            async with AsyncClient(token) as client:
                all_bonds = await client.instruments.bonds()
                return {bond.figi: bond for bond in all_bonds.instruments}
        except Exception as e:
            logger.warning(
                f"Не удалось загрузить облигации через пользователя {settings.telegram_id}: {e}"
            )

    return None


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
    seen_figi: dict[str, BondPrice] = {}

    try:
        async with AsyncClient(token) as client:
            accounts = await client.users.get_accounts()

            for account in accounts.accounts:
                try:
                    portfolio = await client.operations.get_portfolio(account_id=account.id)

                    for position in portfolio.positions:
                        if position.instrument_type != "bond":
                            continue

                        if position.figi in seen_figi:
                            continue

                        bond = bonds_cache.get(position.figi)
                        if not bond:
                            continue

                        current_price = to_float(position.current_price)

                        seen_figi[position.figi] = BondPrice(
                            figi=position.figi,
                            ticker=bond.ticker,
                            name=bond.name,
                            price=current_price,
                            account_name=account.name,
                        )

                except Exception as e:
                    logger.error(f"Ошибка при получении портфеля счёта {account.id}: {e}")
                    continue

    except Exception as e:
        user_part = f" для пользователя {telegram_id}" if telegram_id is not None else ""
        logger.error(f"Ошибка при получении цен облигаций{user_part}: {e}")

    return list(seen_figi.values())
