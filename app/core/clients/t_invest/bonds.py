"""Функции для работы с облигациями через T-Invest API."""

import logging
from dataclasses import dataclass, field
from datetime import datetime

from features.users.repository import BotUserRepository
from t_tech.invest import AsyncClient
from t_tech.invest.schemas import (
    GetAccountsResponse,
    OperationsResponse,
    OperationType,
)

from .common_func import to_float

logger = logging.getLogger(__name__)


@dataclass
class CouponPaymentsByAccount:
    """Информация о платежах купонов по счётам."""

    total_amount: float = 0.0
    accounts: dict[str, float] = field(default_factory=dict)


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
