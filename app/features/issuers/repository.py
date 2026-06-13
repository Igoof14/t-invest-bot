"""Доступ к реестру эмитентов и их облигаций."""

from __future__ import annotations

import logging

from core.clients.moex.moex_bonds import MoexEmitter
from core.database import session_scope
from sqlalchemy import or_, select

from .models import Issuer, IssuerBond

logger = logging.getLogger(__name__)


class IssuerRepository:
    """CRUD реестра эмитентов (компания → ИНН) и их облигаций."""

    @classmethod
    async def upsert_issuer(cls, emitter: MoexEmitter) -> int:
        """Создаёт или обновляет эмитента по ``emitter_id``.

        Args:
            emitter: Данные эмитента из MOEX.

        Returns:
            ``id`` строки эмитента в БД.

        """
        async with session_scope() as session:
            result = await session.execute(
                select(Issuer).where(Issuer.emitter_id == emitter.emitter_id)
            )
            issuer = result.scalar_one_or_none()

            if issuer is None:
                issuer = Issuer(emitter_id=emitter.emitter_id)
                session.add(issuer)

            issuer.inn = emitter.inn
            issuer.title = emitter.title
            issuer.short_title = emitter.short_title
            issuer.ogrn = emitter.ogrn
            issuer.okpo = emitter.okpo
            issuer.legal_address = emitter.legal_address
            issuer.url = emitter.url

            await session.commit()
            await session.refresh(issuer)
            return issuer.id

    @classmethod
    async def upsert_bond(
        cls,
        isin: str,
        figi: str | None = None,
        ticker: str | None = None,
        name: str | None = None,
        issuer_id: int | None = None,
    ) -> None:
        """Создаёт или обновляет облигацию по ``isin``."""
        async with session_scope() as session:
            result = await session.execute(
                select(IssuerBond).where(IssuerBond.isin == isin)
            )
            bond = result.scalar_one_or_none()

            if bond is None:
                bond = IssuerBond(isin=isin)
                session.add(bond)

            bond.figi = figi
            bond.ticker = ticker
            bond.name = name
            bond.issuer_id = issuer_id

            await session.commit()

    @classmethod
    async def get_issuer_by_inn(cls, inn: str) -> Issuer | None:
        """Возвращает эмитента по ИНН или ``None``."""
        async with session_scope() as session:
            result = await session.execute(select(Issuer).where(Issuer.inn == inn))
            issuer = result.scalar_one_or_none()
            if issuer is not None:
                session.expunge(issuer)
            return issuer

    @classmethod
    async def get_issuer_by_isin(cls, isin: str) -> Issuer | None:
        """Возвращает эмитента облигации по её ISIN или ``None``."""
        async with session_scope() as session:
            result = await session.execute(
                select(Issuer)
                .join(IssuerBond, IssuerBond.issuer_id == Issuer.id)
                .where(IssuerBond.isin == isin)
            )
            issuer = result.scalar_one_or_none()
            if issuer is not None:
                session.expunge(issuer)
            return issuer

    @classmethod
    async def list_bonds(cls, issuer_id: int) -> list[IssuerBond]:
        """Возвращает облигации эмитента."""
        async with session_scope() as session:
            result = await session.execute(
                select(IssuerBond).where(IssuerBond.issuer_id == issuer_id)
            )
            bonds = list(result.scalars().all())
            for bond in bonds:
                session.expunge(bond)
            return bonds

    @classmethod
    async def list_issuers(cls) -> list[Issuer]:
        """Возвращает всех эмитентов реестра."""
        async with session_scope() as session:
            result = await session.execute(select(Issuer))
            issuers = list(result.scalars().all())
            for issuer in issuers:
                session.expunge(issuer)
            return issuers

    @classmethod
    async def get_issuers_by_identifiers(
        cls, identifiers: set[str]
    ) -> list[Issuer]:
        """Возвращает эмитентов, чьи облигации совпадают с идентификаторами.

        Args:
            identifiers: Множество figi/ticker/isin (например, из портфеля).

        Returns:
            Список уникальных эмитентов, держащих эти бумаги.

        """
        if not identifiers:
            return []

        ids = list(identifiers)
        async with session_scope() as session:
            result = await session.execute(
                select(Issuer)
                .join(IssuerBond, IssuerBond.issuer_id == Issuer.id)
                .where(
                    or_(
                        IssuerBond.figi.in_(ids),
                        IssuerBond.ticker.in_(ids),
                        IssuerBond.isin.in_(ids),
                    )
                )
                .distinct()
            )
            issuers = list(result.scalars().all())
            for issuer in issuers:
                session.expunge(issuer)
            return issuers
