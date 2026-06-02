"""Тесты репозитория реестра эмитентов."""

from __future__ import annotations

import pytest
from core.clients.moex.moex_bonds import MoexEmitter
from features.issuers.repository import IssuerRepository

pytestmark = pytest.mark.usefixtures("patch_session_scope")


def _emitter(**overrides: object) -> MoexEmitter:
    data: dict[str, object] = {
        "emitter_id": 12606,
        "inn": "1652009537",
        "title": 'ООО "Новые технологии"',
        "short_title": "Новые технологии",
        "secid": "RU000A1075R6",
    }
    data.update(overrides)
    return MoexEmitter(**data)  # type: ignore[arg-type]


async def test_upsert_issuer_creates_and_returns_id() -> None:
    issuer_id = await IssuerRepository.upsert_issuer(_emitter())
    assert isinstance(issuer_id, int)

    issuer = await IssuerRepository.get_issuer_by_inn("1652009537")
    assert issuer is not None
    assert issuer.emitter_id == 12606
    assert issuer.short_title == "Новые технологии"


async def test_upsert_issuer_is_idempotent_by_emitter_id() -> None:
    first = await IssuerRepository.upsert_issuer(_emitter(inn="111"))
    second = await IssuerRepository.upsert_issuer(_emitter(inn="222"))

    assert first == second  # та же строка по emitter_id
    issuers = await IssuerRepository.list_issuers()
    assert len(issuers) == 1
    assert issuers[0].inn == "222"  # данные обновились


async def test_upsert_bond_links_to_issuer() -> None:
    issuer_id = await IssuerRepository.upsert_issuer(_emitter())
    await IssuerRepository.upsert_bond(
        isin="RU000A1075R6",
        figi="BBG00",
        ticker="RU000A1075R6",
        name="НовТех 1Р",
        issuer_id=issuer_id,
    )

    bonds = await IssuerRepository.list_bonds(issuer_id)
    assert len(bonds) == 1
    assert bonds[0].isin == "RU000A1075R6"

    issuer = await IssuerRepository.get_issuer_by_isin("RU000A1075R6")
    assert issuer is not None
    assert issuer.id == issuer_id


async def test_upsert_bond_updates_existing() -> None:
    await IssuerRepository.upsert_bond(isin="RU000A1075R6", name="старое")
    await IssuerRepository.upsert_bond(isin="RU000A1075R6", name="новое", issuer_id=None)

    issuer = await IssuerRepository.get_issuer_by_isin("RU000A1075R6")
    assert issuer is None  # без issuer_id связь не найдётся


async def test_get_issuer_by_inn_returns_none_when_absent() -> None:
    assert await IssuerRepository.get_issuer_by_inn("0000000000") is None
