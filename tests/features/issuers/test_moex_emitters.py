"""Тесты поиска эмитента/ИНН в MoexClient."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from core.clients.moex.moex_bonds import MoexClient, MoexEmitter

_DESCRIPTION = {
    "description": {
        "columns": ["name", "title", "value", "type"],
        "data": [
            ["SECID", "Код", "RU000A1075R6", "string"],
            ["NAME", "Наименование", "Новые технологии", "string"],
            ["EMITTER_ID", "Эмитент", 12606, "number"],
        ],
    }
}

_EMITTER = {
    "emitter": {
        "columns": ["EMITTER_ID", "TITLE", "SHORT_TITLE", "INN", "OGRN", "OKPO", "URL"],
        "data": [
            [
                12606,
                'Общество с ограниченной ответственностью "Новые технологии"',
                'ООО "Новые технологии"',
                "1652009537",
                "1031652403122",
                None,
                "https://nt-lift.com",
            ]
        ],
    }
}


def _client_with_responses(responses: dict[str, Any]) -> tuple[MoexClient, AsyncMock]:
    """Создаёт MoexClient с замоканным _request_json, маршрутизирующим по endpoint."""
    client = MoexClient()

    async def _fake_request(endpoint: str) -> Any:
        if endpoint.startswith("/securities/"):
            return responses["securities"]
        if endpoint.startswith("/emitters/"):
            return responses["emitter"]
        raise AssertionError(f"unexpected endpoint {endpoint}")

    mock = AsyncMock(side_effect=_fake_request)
    client._request_json = mock  # type: ignore[method-assign]
    return client, mock


def test_description_fields_parses_name_value() -> None:
    fields = MoexClient._description_fields(_DESCRIPTION)
    assert fields["EMITTER_ID"] == 12606
    assert fields["NAME"] == "Новые технологии"


def test_description_fields_empty_without_columns() -> None:
    assert MoexClient._description_fields({"description": {}}) == {}


async def test_get_issuer_by_secid_returns_emitter() -> None:
    client, _ = _client_with_responses(
        {"securities": _DESCRIPTION, "emitter": _EMITTER}
    )
    result = await client.get_issuer_by_secid("ru000a1075r6", {})

    assert isinstance(result, MoexEmitter)
    assert result.emitter_id == 12606
    assert result.inn == "1652009537"
    assert result.short_title == 'ООО "Новые технологии"'
    assert result.okpo is None
    assert result.secid == "RU000A1075R6"  # приведён к upper


async def test_get_issuer_by_secid_uses_cache() -> None:
    client, mock = _client_with_responses(
        {"securities": _DESCRIPTION, "emitter": _EMITTER}
    )
    cache: dict[int, MoexEmitter] = {}

    await client.get_issuer_by_secid("RU000A1075R6", cache)
    await client.get_issuer_by_secid("RU000A10BFK4", cache)

    # 2 securities-запроса + всего 1 emitters-запрос (второй взят из кэша).
    endpoints = [call.args[0] for call in mock.call_args_list]
    assert sum(e.startswith("/emitters/") for e in endpoints) == 1
    assert sum(e.startswith("/securities/") for e in endpoints) == 2


async def test_get_issuer_by_secid_none_when_no_emitter_id() -> None:
    no_id = {"description": {"columns": ["name", "value"], "data": [["NAME", "X"]]}}
    client, _ = _client_with_responses({"securities": no_id, "emitter": _EMITTER})
    assert await client.get_issuer_by_secid("RU000AAA", {}) is None


async def test_get_many_issuers_handles_errors() -> None:
    client = MoexClient()

    async def _fake(secid: str, cache: dict) -> MoexEmitter:
        if secid == "BAD":
            raise RuntimeError("boom")
        return MoexEmitter(emitter_id=1, secid=secid)

    client.get_issuer_by_secid = AsyncMock(side_effect=_fake)  # type: ignore[method-assign]

    result = await client.get_many_issuers(["GOOD", "BAD"])
    assert result["GOOD"] is not None
    assert result["BAD"] is None
