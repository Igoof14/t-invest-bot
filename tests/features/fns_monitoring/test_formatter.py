"""Тесты форматирования уведомлений о блокировках ФНС."""

from __future__ import annotations

from features.fns_monitoring.events import (
    BlockingOrder,
    MatchedBond,
    UserBlockAlert,
    UserScanReport,
)
from features.fns_monitoring.formatter import format_fns_alert, format_scan_report


def _plain(msg: str) -> str:
    """Нормализует неразрывные пробелы в обычные для удобства проверок."""
    return msg.replace(" ", " ")


def _orders(n: int, saldo: str = "1647440.01") -> list[BlockingOrder]:
    return [
        BlockingOrder(
            inn="7706",
            block_uid=f"bik{i}:{i}",
            nomer=str(i),
            bik=f"04452{i}",
            kod_osnov="01",
            saldo=saldo,
            entity_name='ООО "Мосрегионлифт"',
        )
        for i in range(n)
    ]


def _alert(n: int) -> UserBlockAlert:
    return UserBlockAlert(
        inn="7706",
        entity_name='ООО "Мосрегионлифт"',
        orders=_orders(n),
        matched_bonds=[MatchedBond(name="Мосрегионлифт БО-02", ticker="RU000A105AJ4")],
    )


def test_alert_is_aggregated_with_copyable_ticker() -> None:
    msg = _plain(format_fns_alert([_alert(7)]))
    assert "Заблокировано счетов: 7" in msg
    assert "Отрицательное сальдо ЕНС: 1 647 440,01 ₽" in msg
    # Тикер обёрнут в <code> — копируется по тапу.
    assert "В вашем портфеле: Мосрегионлифт БО-02 (<code>RU000A105AJ4</code>)" in msg
    # Агрегировано: нет построчного перечисления решений/БИК.
    assert "Решение №" not in msg
    assert "БИК" not in msg


def test_scan_report_aggregated() -> None:
    msg = _plain(format_scan_report(UserScanReport(checked=82, blocked=[_alert(7)])))
    assert "Найдены блокировки счетов (1)" in msg
    assert "Заблокировано счетов: 7" in msg
    assert "<code>RU000A105AJ4</code>" in msg
    assert "Проверено эмитентов: 82." in msg


def test_bond_without_ticker_shows_name_only() -> None:
    alert = UserBlockAlert(
        inn="7706",
        entity_name="ООО ТЕСТ",
        orders=[BlockingOrder(inn="7706", block_uid="b:1", nomer="1")],
        matched_bonds=[MatchedBond(name="ТЕСТ-БО-01", ticker=None)],
    )
    msg = format_fns_alert([alert])
    assert "В вашем портфеле: ТЕСТ-БО-01" in msg
    assert "<code>" not in msg
    assert "сальдо" not in msg.lower()


def test_bond_ticker_equal_name_no_duplicate() -> None:
    # Если тикер совпадает с именем — показываем один <code>, без дубля в скобках.
    alert = UserBlockAlert(
        inn="7706",
        entity_name="X",
        orders=[BlockingOrder(inn="7706", block_uid="b:1", nomer="1")],
        matched_bonds=[MatchedBond(name="RU000A0TEST1", ticker="RU000A0TEST1")],
    )
    msg = format_fns_alert([alert])
    assert "В вашем портфеле: <code>RU000A0TEST1</code>" in msg
    assert "(<code>" not in msg


def test_saldo_uses_max_across_orders() -> None:
    orders = [
        BlockingOrder(inn="7706", block_uid="b:1", nomer="1", saldo="100.00"),
        BlockingOrder(inn="7706", block_uid="b:2", nomer="2", saldo="1647440.01"),
    ]
    alert = UserBlockAlert(inn="7706", entity_name="X", orders=orders, matched_bonds=[])
    msg = _plain(format_fns_alert([alert]))
    assert "1 647 440,01 ₽" in msg
