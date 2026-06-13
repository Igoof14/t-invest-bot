"""Тесты парсинга строк ответа ФНС в доменные блокировки."""

from __future__ import annotations

from features.fns_monitoring.events import parse_rows


def test_parse_rows_empty_when_no_blocks() -> None:
    assert parse_rows("7700000000", {"datePRS": "..."}) == []
    assert parse_rows("7700000000", {"rows": []}) == []


def test_parse_rows_maps_fns_fields() -> None:
    result = {
        "rows": [
            {
                "R": "1",
                "NAIM": 'ООО "ТЕСТ"',
                "INN": "7700000000",
                "BIK": "044525225",
                "NOMER": "12345",
                "DATA": "01.06.2026",
                "DATABEGIN": "20.05.2026",
                "KODOSNOV": "1",
                "SALDOENS": " 100500.50 ",
                "IFNS": "7700",
            }
        ]
    }

    orders = parse_rows("7700000000", result)

    assert len(orders) == 1
    order = orders[0]
    assert order.inn == "7700000000"
    assert order.block_uid == "044525225:12345"
    assert order.entity_name == 'ООО "ТЕСТ"'
    assert order.bik == "044525225"
    assert order.nomer == "12345"
    assert order.decision_date == "01.06.2026"
    assert order.date_begin == "20.05.2026"
    assert order.kod_osnov == "1"
    assert order.saldo == "100500.50"
    assert order.ifns == "7700"


def test_parse_rows_handles_missing_fields() -> None:
    orders = parse_rows("7700000000", {"rows": [{"NOMER": "9"}]})

    assert len(orders) == 1
    assert orders[0].block_uid == "-:9"
    assert orders[0].bik is None
    assert orders[0].saldo is None
