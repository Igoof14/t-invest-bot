"""Разовая проверка эмитентов пользователя по запросу (кнопка).

Плановый непрерывный мониторинг живёт в ``scanner.py``; здесь — только
on-demand сканирование портфеля одного пользователя, распараллеленное по пулу
прокси.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from features.issuers.models import Issuer
from features.issuers.repository import IssuerRepository
from features.ratings.portfolio import get_portfolio_bond_identifiers
from features.users.repository import BotUserRepository

from .client import run
from .events import UserBlockAlert, UserScanReport, parse_rows
from .pipeline import build_issuer_bond_index
from .proxy_pool import load_proxies

logger = logging.getLogger(__name__)

# Число попыток решения капчи на один ИНН.
_RETRIES = 3


class FnsBlockingMonitorService:
    """On-demand проверка эмитентов портфеля пользователя на блокировки счетов."""

    def __init__(self, bot: Bot) -> None:
        """Собирает сервис."""
        self._bot = bot

    async def scan_user(self, telegram_id: int) -> UserScanReport:
        """Разово проверяет всех эмитентов пользователя на текущие блокировки.

        Read-only (ничего не пишет в БД), возвращает полную текущую картину.
        ИНН проверяются параллельно по пулу прокси.

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

        issuers = [
            issuer
            for issuer in await IssuerRepository.get_issuers_by_identifiers(held)
            if issuer.inn
        ]
        if not issuers:
            return UserScanReport()

        proxies = load_proxies()
        sem = asyncio.Semaphore(len(proxies))
        tasks = [
            self._scan_one(issuer, proxies[idx % len(proxies)], held, sem)
            for idx, issuer in enumerate(issuers)
        ]
        results = await asyncio.gather(*tasks)

        report = UserScanReport()
        for checked, alert in results:
            if checked:
                report.checked += 1
            if alert is not None:
                report.blocked.append(alert)
        return report

    async def _scan_one(
        self,
        issuer: Issuer,
        proxy: str | None,
        held: set[str],
        sem: asyncio.Semaphore,
    ) -> tuple[bool, UserBlockAlert | None]:
        """Проверяет одного эмитента; возвращает (проверен?, алерт|None)."""
        inn = issuer.inn or ""
        async with sem:
            try:
                result = await run(inn, retries=_RETRIES, proxy=proxy)
            except ValueError as e:
                logger.info(f"ИНН {inn} пропущен: {e}")
                return (False, None)
            except RuntimeError as e:
                logger.warning(f"ИНН {inn} не проверен: {e}")
                return (False, None)

        orders = parse_rows(inn, result)
        if not orders:
            return (True, None)

        identifiers, bond_by_id = await build_issuer_bond_index(issuer.id)
        matched = held & identifiers
        matched_bonds = sorted(
            {bond_by_id[m] for m in matched if m in bond_by_id},
            key=lambda b: b.name,
        )
        entity_name = issuer.short_title or issuer.title or orders[0].entity_name
        return (
            True,
            UserBlockAlert(
                inn=inn,
                entity_name=entity_name,
                orders=orders,
                matched_bonds=matched_bonds,
            ),
        )
