import os
from datetime import datetime, time, timedelta

from dotenv import load_dotenv
from tinkoff.invest import Client, MoneyValue, OperationType

_ = load_dotenv(".env")
TOKEN = str(os.environ.get("tInvest"))


def cast_money(v: MoneyValue):
    """Cast MoneyValue to float."""
    return v.units + v.nano / 1e9


with Client(TOKEN) as client:
    accounts = client.users.get_accounts()

    amount_total = 0
    today_midnight = datetime.combine(datetime.today().date(), time.min)
    for account in accounts.accounts:
        print(f"Account name: {account.name}")
        operations = client.operations.get_operations(account_id=account.id, from_=today_midnight)

        amount = 0
        for operation in operations.operations:
            if not operation:
                print("No operations")
            if operation.operation_type == OperationType.OPERATION_TYPE_COUPON:
                operation_amount = cast_money(operation.payment)
                amount += operation_amount
        amount_total += amount
        print(f"Payments: {amount:,.2f}")
        print()
    print(f"Total Payments: {amount_total:,.2f}")
