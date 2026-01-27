"""Модуль мониторинга цен облигаций."""

import logging
from dataclasses import dataclass
from enum import Enum

from storage import AlertStorage, BotUserStorage

from .tbank_client import TBankClient

logger = logging.getLogger(__name__)


class AlertType(Enum):
    """Типы алертов."""

    DROP_WARNING = "drop_warning"
    DROP_CRITICAL = "drop_critical"
    RISE_WARNING = "rise_warning"
    RISE_CRITICAL = "rise_critical"


@dataclass
class BondPrice:
    """Информация о цене облигации."""

    figi: str
    ticker: str
    name: str
    price_percent: float
    account_name: str


@dataclass
class PriceAnomaly:
    """Информация об аномалии цены."""

    figi: str
    ticker: str
    name: str
    old_price: float
    new_price: float
    change_percent: float
    alert_type: AlertType
    account_name: str


async def get_portfolio_bond_prices(telegram_id: int) -> list[BondPrice]:
    """Получает текущие цены облигаций из портфеля пользователя.

    Args:
        telegram_id: ID пользователя в Telegram

    Returns:
        Список объектов BondPrice с текущими ценами

    """
    token = await BotUserStorage.get_token_by_telegram_id(telegram_id=telegram_id)
    if not token:
        logger.warning(f"Токен не найден для пользователя {telegram_id}")
        return []

    bond_prices: list[BondPrice] = []

    try:
        async with TBankClient(token) as client:
            # Получаем все облигации для кэша
            all_bonds = await client.get_bonds()
            bonds_cache = {bond.figi: bond for bond in all_bonds}

            accounts = await client.get_accounts()

            for account in accounts:
                try:
                    portfolio = await client.get_portfolio(account_id=account.id)

                    for position in portfolio.positions:
                        if position.instrument_type != "bond":
                            continue

                        bond = bonds_cache.get(position.figi)
                        if not bond:
                            continue

                        # Цена в процентах от номинала
                        current_price = position.current_price.to_float()

                        bond_prices.append(
                            BondPrice(
                                figi=position.figi,
                                ticker=bond.ticker,
                                name=bond.name,
                                price_percent=current_price,
                                account_name=account.name,
                            )
                        )

                except Exception as e:
                    logger.error(f"Ошибка при получении портфеля счёта {account.id}: {e}")
                    continue

    except Exception as e:
        logger.error(f"Ошибка при получении цен облигаций для пользователя {telegram_id}: {e}")

    return bond_prices


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

    for current in current_prices:
        prev = prev_prices_map.get(current.figi)
        if not prev:
            # Новая облигация, нет предыдущей цены для сравнения
            continue

        # Вычисляем процент изменения
        old_price = prev.price_percent
        new_price = current.price_percent

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
    if not await AlertStorage.can_send_more_alerts_today(telegram_id):
        logger.debug(f"Превышен дневной лимит алертов для пользователя {telegram_id}")
        return False

    # Проверяем cooldown
    if not await AlertStorage.can_send_alert(telegram_id, anomaly.figi):
        # Проверяем эскалацию: если последний был warning, а текущий critical - разрешаем
        last_type = await AlertStorage.get_last_alert_type(telegram_id, anomaly.figi)
        if last_type:
            is_escalation = (
                (last_type == AlertType.DROP_WARNING.value
                 and anomaly.alert_type == AlertType.DROP_CRITICAL)
                or
                (last_type == AlertType.RISE_WARNING.value
                 and anomaly.alert_type == AlertType.RISE_CRITICAL)
            )
            if is_escalation:
                logger.debug(f"Разрешаем эскалацию алерта для {anomaly.figi}")
                return True

        logger.debug(f"Cooldown активен для {anomaly.figi}")
        return False

    return True
