"""Модуль мониторинга цен облигаций.

TODO: на следующих этапах рефакторинга detect_anomalies и should_send_alert
переедут в services/price_alert/ (детектор и antispam-политика).
Этот файл — временный шим.
"""

import logging

from services.price_alert.domain import AlertType, PriceAnomaly
from storage import PriceAlertStorage

from .portfolio_prices import BondPrice

logger = logging.getLogger(__name__)

__all__ = [
    "AlertType",
    "BondPrice",
    "PriceAnomaly",
    "detect_anomalies",
    "should_send_alert",
]


def detect_anomalies(
    current_prices: list[BondPrice],
    previous_prices: list,
    settings,
) -> list[PriceAnomaly]:
    """Находит аномалии в изменении цен.

    Args:
        current_prices: Текущие цены облигаций
        previous_prices: Предыдущие цены из БД
        settings: Настройки уведомлений пользователя

    Returns:
        Список найденных аномалий

    """
    anomalies: list[PriceAnomaly] = []

    # Создаём словарь предыдущих цен по figi
    prev_prices_map = {p.figi: p for p in previous_prices}

    # Дедупликация текущих цен: одна и та же облигация на разных счетах имеет одну цену
    current_by_figi = {p.figi: p for p in current_prices}

    for current in current_by_figi.values():
        prev = prev_prices_map.get(current.figi)
        if not prev:
            # Новая облигация, нет предыдущей цены для сравнения
            continue

        # Вычисляем процент изменения
        old_price = prev.price
        new_price = current.price

        if old_price == 0:
            continue

        change_percent = ((new_price - old_price) / old_price) * 100

        alert_type = None

        # Проверяем падение
        if change_percent < 0:
            abs_change = abs(change_percent)
            if abs_change >= settings.drop_critical_threshold:
                alert_type = AlertType.DROP_CRITICAL
            elif abs_change >= settings.drop_warning_threshold:
                alert_type = AlertType.DROP_WARNING

        # Проверяем рост
        elif change_percent > 0:
            if change_percent >= settings.rise_critical_threshold:
                alert_type = AlertType.RISE_CRITICAL
            elif change_percent >= settings.rise_warning_threshold:
                alert_type = AlertType.RISE_WARNING

        if alert_type:
            anomalies.append(
                PriceAnomaly(
                    figi=current.figi,
                    ticker=current.ticker,
                    name=current.name,
                    old_price=old_price,
                    new_price=new_price,
                    change_percent=change_percent,
                    alert_type=alert_type,
                    account_name=current.account_name,
                )
            )

    return anomalies


async def should_send_alert(telegram_id: int, anomaly: PriceAnomaly) -> bool:
    """Проверяет, нужно ли отправлять алерт с учётом anti-spam правил.

    Правила:
    1. Cooldown 4 часа между алертами по одной бумаге
    2. После warning только critical (эскалация)
    3. Максимум 10 уведомлений в день

    Args:
        telegram_id: ID пользователя
        anomaly: Информация об аномалии

    Returns:
        True если алерт можно отправить

    """
    # Проверяем дневной лимит
    if not await PriceAlertStorage.can_send_more_alerts_today(telegram_id):
        logger.debug(f"Превышен дневной лимит алертов для пользователя {telegram_id}")
        return False

    # Проверяем cooldown
    if not await PriceAlertStorage.can_send_alert(telegram_id, anomaly.figi):
        # Проверяем эскалацию: если последний был warning, а текущий critical - разрешаем
        last_type = await PriceAlertStorage.get_last_alert_type(telegram_id, anomaly.figi)
        if last_type:
            is_escalation = (
                last_type == AlertType.DROP_WARNING.value
                and anomaly.alert_type == AlertType.DROP_CRITICAL
            ) or (
                last_type == AlertType.RISE_WARNING.value
                and anomaly.alert_type == AlertType.RISE_CRITICAL
            )
            if is_escalation:
                logger.debug(f"Разрешаем эскалацию алерта для {anomaly.figi}")
                return True

        logger.debug(f"Cooldown активен для {anomaly.figi}")
        return False

    return True
