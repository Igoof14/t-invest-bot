"""Сервис уведомлений об изменении рейтингов НРА."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from aiogram import Bot
from features.issuers.repository import IssuerRepository
from features.ratings.enums import RatingAgency
from features.ratings.repository import RatingAlertSettingsRepository
from features.users.repository import BotUserRepository

from . import config
from .client import NraClient
from .notifier import RatingAlertNotifier
from .repository import NraReleaseRepository
from .schemas import ChangeType, RatingChange, RatingEvent, ReleaseStub
from .t_invest import get_portfolio_bond_identifiers

logger = logging.getLogger(__name__)


@dataclass
class _ResolvedEvent:
    """Рейтинговое событие, привязанное к облигациям эмитента из реестра."""

    event: RatingEvent
    change_type: ChangeType
    # Идентификаторы бумаг эмитента (figi/ticker/isin).
    identifiers: set[str] = field(default_factory=set)
    # Идентификатор бумаги → её отображаемое имя.
    name_by_id: dict[str, str] = field(default_factory=dict)


class RatingAlertService:
    """Оркестратор уведомлений об изменении кредитных рейтингов НРА.

    Раз в ~10 минут опрашивает сайт НРА, находит новые/изменённые рейтинги, по
    ИНН эмитента сопоставляет их с реестром и облигациями, и уведомляет
    пользователей, держащих эти бумаги.
    """

    def __init__(self, bot: Bot, *, notifier: RatingAlertNotifier | None = None) -> None:
        """Собирает сервис.

        Args:
            bot: Экземпляр aiogram-бота.
            notifier: Notifier (для подмены в тестах).

        """
        self._bot = bot
        self._notifier = notifier or RatingAlertNotifier(bot)

    @classmethod
    async def check_rating_updates(cls, bot: Bot) -> None:
        """Точка входа scheduler-джоба — проверяет обновления рейтингов."""
        await cls(bot).run_check()

    async def run_check(self) -> None:
        """Опрашивает НРА и рассылает уведомления по изменениям рейтингов."""
        logger.info("Запуск проверки обновлений рейтингов НРА")

        known = await NraReleaseRepository.get_modified_map()
        is_first_run = not known

        events, change_by_post = await self._poll(known)
        await NraReleaseRepository.upsert_many(events)

        if is_first_run:
            logger.info(
                f"Первый запуск НРА: сохранено {len(events)} релизов, "
                "уведомления не отправляются"
            )
            return

        if not events:
            logger.info("Новых изменений рейтингов НРА нет")
            return

        resolved = await self._resolve_events(events, change_by_post)
        if not resolved:
            logger.info("Изменения рейтингов не относятся к эмитентам из реестра")
            return

        await self._notify_users(resolved)
        logger.info("Проверка обновлений рейтингов НРА завершена")

    async def _poll(
        self, known: dict[int, str | None]
    ) -> tuple[list[RatingEvent], dict[int, ChangeType]]:
        """Опрашивает НРА и возвращает новые/изменённые события с их типом."""
        async with NraClient() as client:
            stubs = await client.iter_release_stubs(config.MAX_PAGES)
            selected, change_by_post = self._select_changed(stubs, known)
            if not selected:
                return [], {}
            events = await client.fetch_many(selected)
        return events, change_by_post

    @staticmethod
    def _select_changed(
        stubs: list[ReleaseStub], known: dict[int, str | None]
    ) -> tuple[list[ReleaseStub], dict[int, ChangeType]]:
        """Отбирает новые/изменённые стабы (с ранней остановкой по modified-desc)."""
        selected: list[ReleaseStub] = []
        change_by_post: dict[int, ChangeType] = {}
        consecutive_known = 0

        for stub in stubs:
            modified_iso = stub.modified.isoformat() if stub.modified else None
            change = NraReleaseRepository.classify(stub.post_id, modified_iso, known)

            if change is None:
                consecutive_known += 1
                if config.EARLY_STOP_KNOWN and consecutive_known >= config.EARLY_STOP_KNOWN:
                    break
                continue

            consecutive_known = 0
            selected.append(stub)
            change_by_post[stub.post_id] = change

        return selected, change_by_post

    @staticmethod
    async def _resolve_events(
        events: list[RatingEvent], change_by_post: dict[int, ChangeType]
    ) -> list[_ResolvedEvent]:
        """Привязывает события к эмитентам реестра и их облигациям."""
        resolved: list[_ResolvedEvent] = []

        for event in events:
            issuer = None
            if event.inn:
                issuer = await IssuerRepository.get_issuer_by_inn(event.inn)
            # Фолбэк: релиз может покрывать несколько выпусков — пробуем каждый.
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
                _ResolvedEvent(
                    event=event,
                    change_type=change_by_post.get(event.post_id, ChangeType.NEW),
                    identifiers=identifiers,
                    name_by_id=name_by_id,
                )
            )

        return resolved

    async def _notify_users(self, resolved: list[_ResolvedEvent]) -> None:
        """Уведомляет подписанных на НРА держателей затронутых бумаг.

        Один проход по подписчикам за полл.
        """
        telegram_ids = await RatingAlertSettingsRepository.list_users_with_alerts_enabled(
            RatingAgency.NRA
        )
        if not telegram_ids:
            return

        for telegram_id in telegram_ids:
            try:
                await self._notify_one(telegram_id, resolved)
            except Exception as e:
                logger.error(f"Ошибка при уведомлении пользователя {telegram_id}: {e}")

    async def _notify_one(self, telegram_id: int, resolved: list[_ResolvedEvent]) -> None:
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
            await self._notifier.send(telegram_id, changes)
