"""Функции для работы с облигациями через T-Invest API.

Канал собирается вручную из ``create_channel`` + ``AsyncServices``, а не через
``AsyncClient``: вход в его контекстный менеджер вызывает ``sentry_sdk.init()``,
который перехватывает Sentry-клиент всего процесса и начинает отправлять наши
трейсбеки в error hub Т-Банка. Во всём остальном вызов идентичен.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime

from features.users.repository import BotUserRepository
from t_tech.invest.async_services import AsyncServices
from t_tech.invest.channels import create_channel
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

    async with create_channel(force_async=True) as channel:
        client = AsyncServices(channel, token=token)
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
