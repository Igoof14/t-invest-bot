"""Детектор аномальных изменений цен облигаций."""

from collections.abc import Iterable

from core.clients.t_invest.portfolio_prices import BondPrice

from .config import AlertThresholds
from .domain import AlertDirection, AlertSeverity, AlertType, PriceAnomaly


def _classify(change_percent: float, thresholds: AlertThresholds) -> AlertType | None:
    """Возвращает тип алерта для изменения цены или None, если порог не пробит."""
    if change_percent < 0:
        abs_change = -change_percent
        if abs_change >= thresholds.drop_critical:
            return AlertType.from_parts(AlertDirection.DROP, AlertSeverity.CRITICAL)
        if abs_change >= thresholds.drop_warning:
            return AlertType.from_parts(AlertDirection.DROP, AlertSeverity.WARNING)
        return None

    if change_percent > 0:
        if change_percent >= thresholds.rise_critical:
            return AlertType.from_parts(AlertDirection.RISE, AlertSeverity.CRITICAL)
        if change_percent >= thresholds.rise_warning:
            return AlertType.from_parts(AlertDirection.RISE, AlertSeverity.WARNING)
        return None

    return None


def detect_anomalies(
    current_prices: Iterable[BondPrice],
    previous_prices: Iterable[BondPrice],
    thresholds: AlertThresholds,
) -> list[PriceAnomaly]:
    """Сравнивает текущие и предыдущие цены, возвращает список аномалий.

    Args:
        current_prices: Свежие цены облигаций из портфеля.
        previous_prices: Предыдущий снимок цен из БД.
        thresholds: Пороги срабатывания алертов.

    Returns:
        Список ``PriceAnomaly`` для бумаг, по которым превышен один из порогов.
        Новые позиции (отсутствующие в предыдущем снимке) пропускаются.

    """
    # Дедупликация: одна и та же бумага на разных счетах имеет одну цену.
    prev_by_figi = {p.figi: p for p in previous_prices}
    current_by_figi = {p.figi: p for p in current_prices}

    anomalies: list[PriceAnomaly] = []
    for current in current_by_figi.values():
        prev = prev_by_figi.get(current.figi)
        if prev is None or prev.price == 0:
            continue

        change_percent = ((current.price - prev.price) / prev.price) * 100
        alert_type = _classify(change_percent, thresholds)
        if alert_type is None:
            continue

        anomalies.append(
            PriceAnomaly(
                figi=current.figi,
                ticker=current.ticker,
                name=current.name,
                old_price=prev.price,
                new_price=current.price,
                change_percent=change_percent,
                alert_type=alert_type,
                account_name=current.account_name,
            )
        )

    return anomalies
