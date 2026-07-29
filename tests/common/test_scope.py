"""Тесты рендера уведомлений для аудитории без токена."""

from __future__ import annotations

from common.scope import MARKET_HINT, AlertScope
from features.fns_monitoring.events import BlockingOrder, MatchedBond, UserBlockAlert
from features.fns_monitoring.formatter import format_fns_alert
from features.price_monitoring.formatter import format_aggregated_alert, format_single_alert
from features.price_monitoring.schemas import AlertType, PriceAnomaly
from features.ratings.formatter import format_rating_alert


def _anomaly(change_pct: float = -9.0) -> PriceAnomaly:
    return PriceAnomaly(
        isin="RU000A0TEST1",
        name="ТЕСТ-БО-01",
        price_pct=91.0,
        prev_close_pct=100.0,
        change_pct=change_pct,
        alert_type=AlertType.DROP_CRITICAL,
    )


def _fns_alert() -> UserBlockAlert:
    return UserBlockAlert(
        inn="7706",
        entity_name="Эмитент X",
        orders=[BlockingOrder(inn="7706", block_uid="b:1", nomer="1")],
        matched_bonds=[MatchedBond(name="ТЕСТ-БО-01", ticker="RU000A0TEST1")],
    )


def test_portfolio_scope_is_the_default() -> None:
    """Без явного scope текст остаётся прежним — совместимость со старым продюсером."""
    assert format_single_alert(_anomaly()) == format_single_alert(
        _anomaly(), AlertScope.PORTFOLIO
    )
    assert MARKET_HINT not in format_single_alert(_anomaly())


def test_market_scope_adds_hint_to_price_alert() -> None:
    assert MARKET_HINT in format_single_alert(_anomaly(), AlertScope.MARKET)


def test_market_scope_drops_portfolio_wording_in_aggregate() -> None:
    """Сводка по рынку не должна советовать «проверить портфель» — его нет."""
    anomalies = [_anomaly(-9.0), _anomaly(-11.0), _anomaly(-13.0)]

    message, _ = format_aggregated_alert(
        anomalies, max_per_severity=5, scope=AlertScope.MARKET
    )

    assert "проверить портфель" not in message
    assert MARKET_HINT in message


def test_market_scope_relabels_fns_bond_list() -> None:
    """Для рыночной аудитории список бумаг — это бумаги эмитента, а не портфель."""
    message = format_fns_alert([_fns_alert()], AlertScope.MARKET)

    assert "В вашем портфеле" not in message
    assert "Облигации эмитента" in message
    assert MARKET_HINT in message


def test_market_scope_changes_rating_header() -> None:
    message = format_rating_alert([], AlertScope.MARKET)

    assert "по вашим облигациям" not in message
    assert MARKET_HINT in message
