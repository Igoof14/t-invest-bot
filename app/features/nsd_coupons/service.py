"""Сервис мониторинга купонов: синк календаря, проверка выплат и дедлайнов."""

from __future__ import annotations

import logging

from aiogram import Bot

from .repository import NsdCouponAlertSettingsRepository, NsdCouponTrackingRepository
from .t_invest import collect_coupon_plans

logger = logging.getLogger(__name__)


class NsdCouponService:
    """Оркестрация мониторинга невыплаченных купонов.

    Экземпляр живёт всё время работы бота и держит карту держателей по ISIN,
    обновляемую при синке календаря (используется при рассылке уведомлений).
    """

    def __init__(self, bot: Bot) -> None:
        """Инициализирует сервис.

        Args:
            bot: Экземпляр бота для отправки уведомлений.
        """
        self._bot = bot
        # ISIN -> множество telegram_id подписчиков, держащих бумагу.
        self._holders_by_isin: dict[str, set[int]] = {}

    async def sync_calendar(self) -> int:
        """Загружает купонный календарь подписчиков и обновляет трекинг.

        Для каждого подписчика собирает плановые купоны из T-Invest, добавляет
        новые в трекинг и пересобирает карту держателей по ISIN.

        Returns:
            Число добавленных в трекинг купонов.
        """
        subscribers = (
            await NsdCouponAlertSettingsRepository.list_users_with_alerts_enabled()
        )
        if not subscribers:
            self._holders_by_isin = {}
            return 0

        holders: dict[str, set[int]] = {}
        all_plans = []
        for telegram_id in subscribers:
            try:
                plans = await collect_coupon_plans(telegram_id)
            except Exception as e:  # noqa: BLE001 — сбой одного юзера не валит синк
                logger.error("Сбор купонов для %s не удался: %s", telegram_id, e)
                continue
            for plan in plans:
                holders.setdefault(plan.isin, set()).add(telegram_id)
            all_plans.extend(plans)

        self._holders_by_isin = holders
        added = await NsdCouponTrackingRepository.upsert_pending(all_plans)
        logger.info(
            "Синк календаря НРД: подписчиков=%d, купонов добавлено=%d, бумаг=%d",
            len(subscribers),
            added,
            len(holders),
        )
        return added
