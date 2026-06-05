"""Агентство-независимый конвейер: классификация → эмитент → портфель → алерт."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from aiogram import Bot
from features.issuers.repository import IssuerRepository
from features.users.repository import BotUserRepository

from .enums import RatingAgency
from .events import ChangeType, RatingChange, RatingEvent, ReleaseStub
from .notifier import RatingAlertNotifier
from .portfolio import get_portfolio_bond_identifiers
from .repository import RatingAlertSettingsRepository, RatingReleaseRepository

logger = logging.getLogger(__name__)


@dataclass
class ResolvedEvent:
    """Рейтинговое событие, привязанное к облигациям эмитента из реестра."""

    event: RatingEvent
    change_type: ChangeType
    identifiers: set[str] = field(default_factory=set)
    name_by_id: dict[str, str] = field(default_factory=dict)


def select_changed(
    stubs: list[ReleaseStub], known: dict[str, str | None], early_stop: int
) -> tuple[list[ReleaseStub], dict[str, ChangeType]]:
    """Отбирает новые/изменённые стабы (ранняя остановка по серии известных)."""
    selected: list[ReleaseStub] = []
    change_by_uid: dict[str, ChangeType] = {}
    consecutive_known = 0

    for stub in stubs:
        modified_iso = stub.modified.isoformat() if stub.modified else None
        change = RatingReleaseRepository.classify(stub.uid, modified_iso, known)

        if change is None:
            consecutive_known += 1
            if early_stop and consecutive_known >= early_stop:
                break
            continue

        consecutive_known = 0
        selected.append(stub)
        change_by_uid[stub.uid] = change

    return selected, change_by_uid


async def resolve_events(
    events: list[RatingEvent], change_by_uid: dict[str, ChangeType]
) -> list[ResolvedEvent]:
    """Привязывает события к эмитентам реестра и их облигациям."""
    resolved: list[ResolvedEvent] = []

    for event in events:
        issuer = None
        if event.inn:
            issuer = await IssuerRepository.get_issuer_by_inn(event.inn)
        for isin in event.isins:
            if issuer is not None:
                break
            issuer = await IssuerRepository.get_issuer_by_isin(isin)

        if issuer is None:
            logger.info(
                f"Эмитент не найден в реестре для релиза {event.url} "
                f"(инн={event.inn}, isins={event.isins})"
            )
            continue

        bonds = await IssuerRepository.list_bonds(issuer.id)
        identifiers: set[str] = set()
        name_by_id: dict[str, str] = {}
        for bond in bonds:
            display_name = bond.name or bond.isin
            for ident in (bond.figi, bond.ticker, bond.isin):
                if ident:
                    identifiers.add(ident)
                    name_by_id[ident] = display_name

        if not identifiers:
            continue

        resolved.append(
            ResolvedEvent(
                event=event,
                change_type=change_by_uid.get(event.uid, ChangeType.NEW),
                identifiers=identifiers,
                name_by_id=name_by_id,
            )
        )

    return resolved


async def notify_subscribers(
    bot: Bot,
    agency: RatingAgency,
    resolved: list[ResolvedEvent],
    notifier: RatingAlertNotifier | None = None,
) -> None:
    """Уведомляет подписчиков агентства, держащих затронутые бумаги."""
    notifier = notifier or RatingAlertNotifier(bot)
    telegram_ids = await RatingAlertSettingsRepository.list_users_with_alerts_enabled(agency)
    if not telegram_ids:
        return

    for telegram_id in telegram_ids:
        try:
            await _notify_one(notifier, agency, telegram_id, resolved)
        except Exception as e:
            logger.error(f"Ошибка при уведомлении пользователя {telegram_id}: {e}")


async def _notify_one(
    notifier: RatingAlertNotifier,
    agency: RatingAgency,
    telegram_id: int,
    resolved: list[ResolvedEvent],
) -> None:
    """Сопоставляет портфель пользователя с изменениями и шлёт алерт."""
    token = await BotUserRepository.get_token_by_telegram_id(telegram_id)
    if not token:
        return

    held = await get_portfolio_bond_identifiers(token, telegram_id=telegram_id)
    if not held:
        return

    changes: list[RatingChange] = []
    for item in resolved:
        matched = held & item.identifiers
        if not matched:
            continue
        matched_names = sorted({item.name_by_id[m] for m in matched if m in item.name_by_id})
        changes.append(
            RatingChange(
                event=item.event,
                change_type=item.change_type,
                matched_bond_names=matched_names,
            )
        )

    if changes:
        await notifier.send(telegram_id, agency.display_name, changes)
