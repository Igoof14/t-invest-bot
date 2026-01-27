"""Функции для работы с T-Invest API."""

from datetime import datetime

from storage import BotUserStorage

from .models import OperationType
from .tbank_client import TBankClient


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


async def check_token(token: str) -> bool:
    """Проверяет, что токен действителен.

    Args:
        token: API токен

    Returns:
        True если токен валиден

    """
    try:
        async with TBankClient(token) as client:
            await client.get_info()
        return True
    except Exception:
        return False
