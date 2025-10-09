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


with Client(TOKEN) as client:
    # today_midnight = datetime.combine(datetime.today().date(), time.min)
    yesterday_midnight = datetime.combine((datetime.today() - timedelta(days=1)).date(), time.min)
    for account in accounts.accounts:
        print(f"Account name: {account.name}")
        operations = client.operations.get_operations(
            account_id=account.id, from_=yesterday_midnight
        )

        amount = 0
        for operation in operations.operations:
            if not operation:
                print("No operations")
            if operation.operation_type == OperationType.OPERATION_TYPE_COUPON:
                amount = cast_money(operation.payment)

        print(f"Payments: {amount}")

        print()
