"""Общие шаги конвейера блокировок ФНС: холдинги, индексы, матчинг."""

from __future__ import annotations

from features.issuers.models import Issuer
from features.issuers.repository import IssuerRepository
from features.ratings.portfolio import get_portfolio_bond_identifiers
from features.users.repository import BotUserRepository

from .events import BlockingOrder, ResolvedBlock, UserBlockAlert


async def collect_holdings(subscribers: list[int]) -> dict[int, set[str]]:
    """Собирает идентификаторы облигаций из портфеля каждого подписчика.

    Args:
        subscribers: Telegram ID подписчиков.

    Returns:
        Отображение ``{telegram_id: множество figi/ticker/isin}``.

    """
    held_by_user: dict[int, set[str]] = {}
    for telegram_id in subscribers:
        token = await BotUserRepository.get_token_by_telegram_id(telegram_id)
        if not token:
            continue
        held = await get_portfolio_bond_identifiers(token, telegram_id=telegram_id)
        if held:
            held_by_user[telegram_id] = held
    return held_by_user


async def build_issuer_bond_index(issuer_id: int) -> tuple[set[str], dict[str, str]]:
    """Возвращает идентификаторы облигаций эмитента и их отображаемые имена."""
    bonds = await IssuerRepository.list_bonds(issuer_id)
    identifiers: set[str] = set()
    name_by_id: dict[str, str] = {}
    for bond in bonds:
        display_name = bond.name or bond.isin
        for ident in (bond.figi, bond.ticker, bond.isin):
            if ident:
                identifiers.add(ident)
                name_by_id[ident] = display_name
    return identifiers, name_by_id


async def resolve_block(issuer: Issuer, new_orders: list[BlockingOrder]) -> ResolvedBlock:
    """Привязывает новые блокировки эмитента к его облигациям из реестра."""
    identifiers, name_by_id = await build_issuer_bond_index(issuer.id)
    entity_name = issuer.short_title or issuer.title or new_orders[0].entity_name
    return ResolvedBlock(
        inn=issuer.inn or "",
        entity_name=entity_name,
        new_orders=new_orders,
        identifiers=identifiers,
        name_by_id=name_by_id,
    )


def match_alerts(held: set[str], blocks: list[ResolvedBlock]) -> list[UserBlockAlert]:
    """Отбирает блокировки, затрагивающие бумаги пользователя.

    Args:
        held: Идентификаторы облигаций из портфеля пользователя.
        blocks: Новые блокировки эмитентов (с индексом их облигаций).

    Returns:
        Список ``UserBlockAlert`` по пересечению портфеля с затронутыми бумагами.

    """
    alerts: list[UserBlockAlert] = []
    for block in blocks:
        matched = held & block.identifiers
        if not matched:
            continue
        matched_names = sorted(
            {block.name_by_id[m] for m in matched if m in block.name_by_id}
        )
        alerts.append(
            UserBlockAlert(
                inn=block.inn,
                entity_name=block.entity_name,
                orders=block.new_orders,
                matched_bond_names=matched_names,
            )
        )
    return alerts
