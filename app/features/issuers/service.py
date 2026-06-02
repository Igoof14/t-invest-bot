"""Сервис синхронизации реестра эмитентов с MOEX.

Тянет все облигации из T-Invest, по каждой ищет эмитента и ИНН на MOEX ISS
и сохраняет компании и их облигации в основную БД.
"""

from __future__ import annotations

import logging
from typing import Any

from core.clients.moex.moex_bonds import MoexClient
from core.config import config
from features.users.repository import BotUserRepository
from t_tech.invest import AsyncClient

from .repository import IssuerRepository

logger = logging.getLogger(__name__)


class IssuerSyncService:
    """Оркестратор синхронизации реестра эмитентов."""

    @classmethod
    async def _resolve_token(cls) -> str | None:
        """Возвращает T-Invest токен для синка.

        Приоритет — сервисный ``config.t_invest_token``; если его нет, берётся
        токен любого активного пользователя.
        """
        if config.t_invest_token:
            return config.t_invest_token.get_secret_value()

        for telegram_id in await BotUserRepository.get_all_active_users():
            user_token = await BotUserRepository.get_token_by_telegram_id(telegram_id)
            if user_token:
                return user_token
        return None

    @classmethod
    async def _fetch_all_bonds(cls, token: str) -> list[Any]:
        """Загружает все облигации с биржи через T-Invest."""
        async with AsyncClient(token) as client:
            response = await client.instruments.bonds()
            return list(response.instruments)

    @classmethod
    async def sync_all_issuers(cls) -> tuple[int, int]:
        """Синхронизирует реестр эмитентов и их облигаций.

        Returns:
            Кортеж ``(сохранено_эмитентов, обработано_облигаций)``.

        """
        token = await cls._resolve_token()
        if not token:
            logger.warning("Нет T-Invest токена для синхронизации эмитентов")
            return 0, 0

        bonds = await cls._fetch_all_bonds(token)
        bonds_by_isin = {bond.isin: bond for bond in bonds if getattr(bond, "isin", None)}
        isins = list(bonds_by_isin)
        logger.info(f"Получено {len(isins)} облигаций из T-Invest")

        async with MoexClient() as moex:
            issuers_by_isin = await moex.get_many_issuers(isins)

        issuer_id_by_emitter: dict[int, int] = {}
        issuers_count = 0
        bonds_count = 0

        for isin, bond in bonds_by_isin.items():
            emitter = issuers_by_isin.get(isin)
            issuer_id: int | None = None

            if emitter is not None:
                issuer_id = issuer_id_by_emitter.get(emitter.emitter_id)
                if issuer_id is None:
                    issuer_id = await IssuerRepository.upsert_issuer(emitter)
                    issuer_id_by_emitter[emitter.emitter_id] = issuer_id
                    issuers_count += 1

            await IssuerRepository.upsert_bond(
                isin=isin,
                figi=getattr(bond, "figi", None),
                ticker=getattr(bond, "ticker", None),
                name=getattr(bond, "name", None),
                issuer_id=issuer_id,
            )
            bonds_count += 1

        logger.info(
            f"Синхронизация реестра завершена: эмитентов={issuers_count}, "
            f"облигаций={bonds_count}"
        )
        return issuers_count, bonds_count
