"""Оркестратор мониторинга блокировок счетов ФНС.

Конвейер: подписчики → портфели → эмитенты (+ИНН) → проверка ФНС →
дедуп → рассылка держателям.
"""

from __future__ import annotations

import logging

from aiogram import Bot
from features.issuers.models import Issuer
from features.issuers.repository import IssuerRepository
from features.ratings.portfolio import get_portfolio_bond_identifiers
from features.users.repository import BotUserRepository

from .events import (
    BlockingOrder,
    ResolvedBlock,
    UserBlockAlert,
    UserScanReport,
    parse_rows,
)
from .notifier import FnsBlockNotifier
from .recerence import run
from .repository import FnsAlertSettingsRepository, FnsBlockingRepository

logger = logging.getLogger(__name__)

# Число попыток решения капчи на один ИНН в фоновом прогоне.
_RETRIES = 3


class FnsBlockingMonitorService:
    """Проверяет ИНН эмитентов, держимых подписчиками, на блокировки счетов."""

    def __init__(self, bot: Bot, *, notifier: FnsBlockNotifier | None = None) -> None:
        """Собирает сервис."""
        self._bot = bot
        self._notifier = notifier or FnsBlockNotifier(bot)

    @classmethod
    async def check_blocks(cls, bot: Bot) -> None:
        """Точка входа scheduler-джоба."""
        await cls(bot).run_check()

    async def run_check(self) -> None:
        """Опрашивает ФНС по бумагам подписчиков и рассылает уведомления."""
        logger.info("Запуск проверки блокировок счетов ФНС")

        subscribers = await FnsAlertSettingsRepository.list_users_with_alerts_enabled()
        if not subscribers:
            logger.info("Нет подписчиков на блокировки ФНС")
            return

        held_by_user = await self._collect_holdings(subscribers)
        all_held: set[str] = set().union(*held_by_user.values()) if held_by_user else set()
        if not all_held:
            logger.info("Ни у одного подписчика нет облигаций для проверки")
            return

        issuers = await IssuerRepository.get_issuers_by_identifiers(all_held)
        resolved = await self._check_issuers(issuers)
        if not resolved:
            logger.info("Новых блокировок счетов не обнаружено")
            return

        await self._notify(held_by_user, resolved)
        logger.info("Проверка блокировок счетов ФНС завершена")

    async def _collect_holdings(self, subscribers: list[int]) -> dict[int, set[str]]:
        """Собирает идентификаторы облигаций из портфеля каждого подписчика."""
        held_by_user: dict[int, set[str]] = {}
        for telegram_id in subscribers:
            token = await BotUserRepository.get_token_by_telegram_id(telegram_id)
            if not token:
                continue
            held = await get_portfolio_bond_identifiers(token, telegram_id=telegram_id)
            if held:
                held_by_user[telegram_id] = held
        return held_by_user

    async def _check_issuers(self, issuers: list[Issuer]) -> list[ResolvedBlock]:
        """Проверяет каждого эмитента в ФНС и возвращает новые блокировки."""
        resolved: list[ResolvedBlock] = []
        for issuer in issuers:
            if not issuer.inn:
                continue

            try:
                result = await run(issuer.inn, retries=_RETRIES)
            except ValueError as e:
                logger.info(f"ИНН {issuer.inn} пропущен: {e}")
                continue
            except RuntimeError as e:
                logger.warning(f"ИНН {issuer.inn} не проверен: {e}")
                continue

            orders = parse_rows(issuer.inn, result)
            had_history = await FnsBlockingRepository.has_any(issuer.inn)
            new_orders = await FnsBlockingRepository.sync(issuer.inn, orders)

            if not had_history:
                logger.info(
                    f"ИНН {issuer.inn}: первичная фиксация "
                    f"({len(orders)} блокировок), без уведомления"
                )
                continue

            if not new_orders:
                continue

            block = await self._resolve_block(issuer, new_orders)
            if block.identifiers:
                resolved.append(block)
        return resolved

    @classmethod
    async def _resolve_block(cls, issuer: Issuer, new_orders: list[BlockingOrder]) -> ResolvedBlock:
        """Привязывает новые блокировки эмитента к его облигациям из реестра."""
        identifiers, name_by_id = await cls._issuer_bond_index(issuer.id)
        entity_name = issuer.short_title or issuer.title or new_orders[0].entity_name
        return ResolvedBlock(
            inn=issuer.inn or "",
            entity_name=entity_name,
            new_orders=new_orders,
            identifiers=identifiers,
            name_by_id=name_by_id,
        )

    @staticmethod
    async def _issuer_bond_index(
        issuer_id: int,
    ) -> tuple[set[str], dict[str, str]]:
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

    async def scan_user(self, telegram_id: int) -> UserScanReport:
        """Разово проверяет всех эмитентов пользователя на текущие блокировки.

        В отличие от планового прогона, ничего не пишет в БД (read-only) и
        возвращает полную текущую картину, а не только новые блокировки.

        Args:
            telegram_id: Telegram ID пользователя.

        Returns:
            Отчёт ``UserScanReport`` для показа пользователю.

        """
        logger.info(f"Разовая проверка эмитентов пользователя {telegram_id}")

        token = await BotUserRepository.get_token_by_telegram_id(telegram_id)
        if not token:
            return UserScanReport(no_token=True)

        held = await get_portfolio_bond_identifiers(token, telegram_id=telegram_id)
        if not held:
            return UserScanReport(no_bonds=True)

        issuers = await IssuerRepository.get_issuers_by_identifiers(held)
        report = UserScanReport()
        for issuer in issuers:
            if not issuer.inn:
                continue

            try:
                result = await run(issuer.inn, retries=_RETRIES)
            except ValueError as e:
                logger.info(f"ИНН {issuer.inn} пропущен: {e}")
                continue
            except RuntimeError as e:
                logger.warning(f"ИНН {issuer.inn} не проверен: {e}")
                continue

            report.checked += 1
            orders = parse_rows(issuer.inn, result)
            if not orders:
                continue

            identifiers, name_by_id = await self._issuer_bond_index(issuer.id)
            matched = held & identifiers
            matched_names = sorted({name_by_id[m] for m in matched if m in name_by_id})
            entity_name = issuer.short_title or issuer.title or orders[0].entity_name
            report.blocked.append(
                UserBlockAlert(
                    inn=issuer.inn,
                    entity_name=entity_name,
                    orders=orders,
                    matched_bond_names=matched_names,
                )
            )

        return report

    async def _notify(
        self, held_by_user: dict[int, set[str]], resolved: list[ResolvedBlock]
    ) -> None:
        """Рассылает каждому подписчику блокировки по его бумагам."""
        for telegram_id, held in held_by_user.items():
            alerts: list[UserBlockAlert] = []
            for block in resolved:
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

            if alerts:
                try:
                    await self._notifier.send(telegram_id, alerts)
                except Exception as e:
                    logger.error(f"Ошибка при уведомлении {telegram_id}: {e}")
