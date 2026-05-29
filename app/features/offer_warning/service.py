"""Сервис уведомлений о приближающихся офертах облигаций."""

from __future__ import annotations

import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore
from apscheduler.triggers.date import DateTrigger  # type: ignore
from core.clients.moex.moex_bonds import MoexBondOffer, MoexClient
from features.users.repository import BotUserRepository

from .notifier import OfferAlertNotifier
from .repository import OfferSettingsRepository
from .t_invest import get_portfolio_bond_isins

logger = logging.getLogger(__name__)

MSK_TZ = ZoneInfo("Europe/Moscow")


class OfferAlertService:
    """Оркестратор уведомлений об офертах.

    Ежедневно в 06:00 МСК вычисляет, у каких пользователей сегодня
    наступает alert-порог по оферте, и регистрирует DateTrigger-джоб
    на точное время уведомления каждого пользователя.
    """

    @classmethod
    async def schedule_daily_jobs(cls, bot: Bot, scheduler: AsyncIOScheduler) -> None:
        """Регистрирует DateTrigger-джобы для пользователей с офертами на сегодня.

        Идемпотентен: повторный вызов (например, при рестарте бота) не создаёт
        дублей — джоб с существующим ID APScheduler игнорирует.

        Args:
            bot: Экземпляр aiogram-бота.
            scheduler: Запущенный экземпляр APScheduler.

        """
        logger.info("Расчёт уведомлений об офертах на сегодня")

        telegram_ids = await OfferSettingsRepository.list_users_with_alerts_enabled()
        if not telegram_ids:
            logger.info("Нет пользователей с включёнными уведомлениями об офертах")
            return

        logger.info(f"Расчёт уведомлений об офертах, найдено={len(telegram_ids)}")
        today = datetime.now(MSK_TZ).date()
        scheduled_count = 0

        for telegram_id in telegram_ids:
            try:
                offers = await cls._get_matching_offers(telegram_id, today)
                logger.info(f"Найдено {len(offers)} оферт для {telegram_id}")
                if not offers:
                    continue

                settings = await OfferSettingsRepository.get(telegram_id)
                if settings is None:
                    continue

                notification_dt = datetime.combine(today, settings.notification_time, tzinfo=MSK_TZ)
                if notification_dt <= datetime.now(MSK_TZ):
                    logger.info(f"Время уведомления для {telegram_id} уже прошло — пропускаем")
                    continue

                job_id = f"offer_alert_{telegram_id}_{today}"
                if scheduler.get_job(job_id) is not None:
                    logger.debug(f"Джоб {job_id} уже зарегистрирован")
                    continue

                scheduler.add_job(
                    cls.send_notifications,
                    DateTrigger(run_date=notification_dt),
                    id=job_id,
                    kwargs={"bot": bot, "telegram_id": telegram_id, "offers": offers},
                )
                scheduled_count += 1
                logger.info(
                    f"Запланировано уведомление для {telegram_id} "
                    f"в {settings.notification_time} МСК ({len(offers)} оферт(ы))"
                )

            except Exception as e:
                logger.error(f"Ошибка при планировании уведомления для {telegram_id}: {e}")

        logger.info(f"Зарегистрировано {scheduled_count} уведомлений на сегодня")

    @classmethod
    async def send_notifications(
        cls, bot: Bot, telegram_id: int, offers: list[MoexBondOffer]
    ) -> None:
        """Отправляет уведомление пользователю. Вызывается DateTrigger-джобом.

        Args:
            bot: Экземпляр aiogram-бота.
            telegram_id: Telegram ID получателя.
            offers: Список оферт для уведомления.

        """
        notifier = OfferAlertNotifier(bot)
        await notifier.send(telegram_id, offers)

    @classmethod
    async def _get_matching_offers(cls, telegram_id: int, today: date) -> list[MoexBondOffer]:
        """Возвращает PUT-оферты из портфеля пользователя, совпадающие с его alert-порогами.

        Args:
            telegram_id: Telegram ID пользователя.
            today: Текущая дата МСК.

        Returns:
            Список MoexBondOffer. Пустой если совпадений нет.

        """
        settings = await OfferSettingsRepository.get(telegram_id)
        if settings is None:
            return []

        token = await BotUserRepository.get_token_by_telegram_id(telegram_id)
        if not token:
            logger.warning(f"Токен не найден для пользователя {telegram_id}")
            return []

        isins = await get_portfolio_bond_isins(token, telegram_id=telegram_id)
        if not isins:
            logger.debug(f"Нет облигаций в портфеле пользователя {telegram_id}")
            return []
        logger.info(f"Найдено {len(isins)} облигаций в портфеле пользователя {telegram_id}")

        async with MoexClient() as moex_client:
            offers_by_isin = await moex_client.get_many_next_bond_offers(isins)

        alert_thresholds = {settings.first_alert, settings.second_alert}
        logger.info(f"alert_thresholds={alert_thresholds}")

        result: list[MoexBondOffer] = []

        for offer in offers_by_isin.values():
            if offer is None:
                continue
            if (offer.offerdate - today).days in alert_thresholds:
                result.append(offer)

        return result
