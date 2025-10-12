import os
from datetime import date, datetime, time, timedelta

from dotenv import load_dotenv
from tinkoff.invest import Client, MoneyValue, OperationType

_ = load_dotenv(".env")
TOKEN = str(os.environ.get("tInvest"))


def cast_money(v: MoneyValue):
    """Cast MoneyValue to float."""
    return v.units + v.nano / 1e9


def get_coupon_payment_today(start_datetime: datetime):
    """Get payment amount for today."""
    with Client(TOKEN) as client:
        accounts = client.users.get_accounts()

        total_amount = 0
        message = "<b>Купонные выплаты за сегодня:</b>\n\n"

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
