from datetime import datetime

from storage import BotUserStorage
from tinkoff.invest import Client, MoneyValue, OperationType


def cast_money(v: MoneyValue):
    """Cast MoneyValue to float."""
    return v.units + v.nano / 1e9


async def get_coupon_payment(user_id: int, start_datetime: datetime):
    """Get payment amount for today."""
    TOKEN = await BotUserStorage.get_token_by_telegram_id(telegram_id=user_id)

    with Client(str(TOKEN)) as client:
        accounts = client.users.get_accounts()

        total_amount = 0
        message = ""
        for account in accounts.accounts:
            operations = client.operations.get_operations(
                account_id=account.id, from_=start_datetime
            )

            account_amount = 0
            if not operations.operations:
                message += f"<b>{account.name}</b>: 0₽\n"
                continue

            for operation in operations.operations:
                if operation.operation_type == OperationType.OPERATION_TYPE_COUPON:
                    operation_amount = cast_money(operation.payment)
                    account_amount += operation_amount

            total_amount += account_amount
            message += f"<b>{account.name}</b>: {account_amount:,.2f}₽\n"

        message += f"\n<b>Сумма выплат:</b> {total_amount:,.2f}₽"

        return message


def check_token(token: str) -> bool:
    """Проверяет, что токен действителен."""
    try:
        with Client(token) as client:
            _ = client.users.get_info()
            ...
        return True

    except Exception as e:
        print(f"Ошибка при проверке токена: {e}")
        return False
