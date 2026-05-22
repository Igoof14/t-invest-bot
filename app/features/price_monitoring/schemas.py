from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BondPrice:
    """Снимок цены облигации в портфеле пользователя."""

    figi: str
    ticker: str
    name: str
    price: float
    account_name: str
