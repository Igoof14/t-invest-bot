import os

from dotenv import load_dotenv
from tinkoff.invest import Client, MoneyValue

_ = load_dotenv(".env")
TOKEN = str(os.environ.get("tInvest"))


def cast_money(v: MoneyValue):
    return v.units + v.nano / 1e9


# with Client(TOKEN) as client:
#     accounts = client.users.get_accounts()

# for i in accounts.accounts:
#     print(i)
#     print() 2045796893
#
with Client(TOKEN) as client:
    accounts = client.operations.get_portfolio(account_id="2045796893")

print(f"Всего в акциях: {cast_money(accounts.total_amount_shares):,.2f}")
print(f"Всего в облигациях: {cast_money(accounts.total_amount_bonds):,.2f}")
print(f"Всего в etf: {cast_money(accounts.total_amount_etf):,.2f}")
print(f"Всего в валютах: {cast_money(accounts.total_amount_currencies):,.2f}")
print(f"Всего в фьючерсах: {cast_money(accounts.total_amount_futures):,.2f}")
print()

for position in accounts.positions:
    print(position)
    print()
