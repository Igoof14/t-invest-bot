"""Сервис мониторинга цен и отправки уведомлений об аномалиях."""

import logging

from aiogram import Bot
from t_tech.invest.schemas import Bond

from ..users.repository import BotUserRepository
from .anti_spam import AntiSpamPolicy
from .config import DEFAULT_POLICY, AlertPolicyConfig, AlertThresholds
from .detector import detect_anomalies
from .models import PriceAlertSettings
from .notifier import PriceAlertNotifier
from .repository import (
    AlertSettingsRepository,
    PriceHistoryRepository,
    SentAlertRepository,
)
from .schemas import PriceAnomaly
from .t_invest import fetch_portfolio_bond_prices, get_bonds

logger = logging.getLogger(__name__)


class PriceAlertService:
    """Оркестратор мониторинга цен.

    Сервис склеивает компоненты фичи — репозитории, детектор аномалий,
    антиспам-политику и notifier. Зависимости передаются через конструктор
    (DI), что упрощает тестирование и подмену реализаций.

    Для обратной совместимости со старым scheduler-кодом оставлен
    classmethod :meth:`check_price_anomalies`, создающий сервис с
    дефолтными зависимостями.
    """

    def __init__(
        self,
        bot: Bot,
        *,
        settings_repo: type[AlertSettingsRepository] = AlertSettingsRepository,
        history_repo: type[PriceHistoryRepository] = PriceHistoryRepository,
        sent_repo: type[SentAlertRepository] = SentAlertRepository,
        anti_spam: AntiSpamPolicy | None = None,
        notifier: PriceAlertNotifier | None = None,
        config: AlertPolicyConfig = DEFAULT_POLICY,
    ):
        """Собирает сервис с указанными зависимостями."""
        self._bot = bot
        self._settings_repo = settings_repo
        self._history_repo = history_repo
        self._sent_repo = sent_repo
        self._config = config
        self._anti_spam = anti_spam or AntiSpamPolicy(sent_repo=sent_repo, config=config)
        self._notifier = notifier or PriceAlertNotifier(bot=bot, sent_repo=sent_repo)

    @classmethod
    async def check_price_anomalies(cls, bot: Bot) -> None:
        """Точка входа scheduler-джоба — проверяет цены всех пользователей."""
        await cls(bot).run_check()

    @classmethod
    async def run_daily_cleanup(cls, bot: Bot, *, days_to_keep: int = 7) -> None:
        """Точка входа дневного scheduler-джоба — удаляет старые записи цен и алертов."""
        await cls(bot).cleanup(days_to_keep=days_to_keep)

    async def cleanup(self, *, days_to_keep: int = 7) -> None:
        """Удаляет исторические записи старше указанного количества дней."""
        logger.info(f"Запуск очистки старых данных (храним {days_to_keep} дн.)")
        await self._history_repo.cleanup_older_than(days_to_keep=days_to_keep)
        await self._sent_repo.cleanup_older_than(days_to_keep=days_to_keep)
        logger.info("Очистка старых данных завершена")

    async def run_check(self) -> None:
        """Проверяет цены для всех пользователей с включенными уведомлениями."""
        logger.info("Запуск проверки аномалий цен облигаций")

        users_settings = await self._settings_repo.list_users_with_alerts_enabled()
        if not users_settings:
            logger.info("Нет пользователей с включенными уведомлениями")
            return

        logger.info(f"Проверка цен для {len(users_settings)} пользователей")

        bonds_cache = await get_bonds()
        if not bonds_cache:
            logger.error("Не удалось загрузить справочник облигаций, пропуск проверки")
            return

        for settings in users_settings:
            try:
                await self._check_user_portfolio(settings.telegram_id, settings, bonds_cache)
            except Exception as e:
                logger.error(
                    f"Ошибка при проверке портфеля пользователя {settings.telegram_id}: {e}"
                )

        logger.info("Проверка аномалий цен завершена")

    async def _check_user_portfolio(
        self, telegram_id: int, settings: PriceAlertSettings, bonds_cache: dict[str, Bond]
    ) -> None:
        """Проверяет портфель одного пользователя на аномалии."""
        token = await BotUserRepository.get_token_by_telegram_id(telegram_id=telegram_id)
        if not token:
            logger.warning(f"Токен не найден для пользователя {telegram_id}")
            return

        current_prices = await fetch_portfolio_bond_prices(
            token, bonds_cache, telegram_id=telegram_id
        )
        if not current_prices:
            logger.debug(f"Нет облигаций в портфеле пользователя {telegram_id}")
            return

        previous_prices = await self._history_repo.get_latest(telegram_id)
        if previous_prices:
            thresholds = AlertThresholds.from_settings(settings)
            anomalies = detect_anomalies(current_prices, previous_prices, thresholds)
            if anomalies:
                await self._send_alerts(telegram_id, anomalies)

        await self._history_repo.save_snapshot(telegram_id, current_prices)

    async def _send_alerts(self, telegram_id: int, anomalies: list[PriceAnomaly]) -> None:
        """Прогоняет аномалии через антиспам и делегирует отправку notifier'у."""
        alerts_to_send = await self._anti_spam.filter(telegram_id, anomalies)
        if not alerts_to_send:
            return

        if len(alerts_to_send) > self._config.aggregate_threshold:
            await self._notifier.send_aggregated(
                telegram_id,
                alerts_to_send,
                max_per_severity=self._config.max_aggregated_per_severity,
            )
        else:
            for anomaly in alerts_to_send:
                await self._notifier.send_single(telegram_id, anomaly)
