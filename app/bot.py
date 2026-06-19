import asyncio
import logging

from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore
from apscheduler.triggers.cron import CronTrigger  # type: ignore
from common.utils.bot_utils import BotUtils
from core.config import config
from core.database import db_manager
from core.enums import ReportType
from features.base import base_handlers
from features.broadcast import router as broadcast_router
from features.coupons import coupon_handlers
from features.fns_monitoring import router as fns_router
from features.fns_monitoring.menu import SECTION as fns_section
from features.fns_monitoring.scanner import FnsScanner
from features.issuers import IssuerSyncService
from features.menu import register_section
from features.menu import router as menu_router
from features.nsd_coupons import NsdCouponService
from features.nsd_coupons import router as nsd_coupons_router
from features.nsd_coupons.menu import SECTION as nsd_coupons_section
from features.offer_warning import OfferAlertService
from features.offer_warning import handlers as offer_warning_handlers
from features.offer_warning.menu import SECTION as offer_section
from features.onboarding import router as onboarding_router
from features.price_monitoring import PriceAlertService, price_alert_handlers
from features.price_monitoring.menu import SECTION as price_section
from features.ratings import router as ratings_router
from features.ratings.menu import SECTION as ratings_section
from features.ratings.rating_nkr import NkrRatingAlertService
from features.ratings.rating_nra import NraRatingAlertService
from features.reports import ReportService
from features.users import users_handlers

logging.basicConfig(level=logging.INFO)

bot = Bot(token=config.bot_token.get_secret_value())
dp = Dispatcher()

# Удержание фоновых объектов/задач на время жизни процесса (защита от GC).
_BACKGROUND: list[object] = []


async def main():
    """Запуск бота."""
    await db_manager.create_tables()

    # Регистрируем секции хаба «Уведомления» (порядок = порядок в меню).
    register_section(price_section)
    register_section(offer_section)
    register_section(ratings_section)
    # register_section(fns_section)
    register_section(nsd_coupons_section)

    dp.include_routers(
        base_handlers.router,
        broadcast_router,
        onboarding_router,
        price_alert_handlers.router,
        offer_warning_handlers.router,
        coupon_handlers.router,
        users_handlers.router,
        ratings_router,
        fns_router,
        nsd_coupons_router,
        menu_router,
    )

    await BotUtils.set_commands(bot)
    await BotUtils.set_descriptions(bot)
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

    scheduler.add_job(
        ReportService.send_report,
        CronTrigger(day_of_week="mon-fri", hour=18, minute=10, timezone="Europe/Moscow"),
        kwargs={"bot": bot, "report_type": ReportType.DAILY},
    )

    scheduler.add_job(
        ReportService.send_report,
        CronTrigger(day_of_week="fri", hour=18, minute=10, second=1, timezone="Europe/Moscow"),
        kwargs={"bot": bot, "report_type": ReportType.WEEKLY},
    )

    scheduler.add_job(
        PriceAlertService.check_price_anomalies,
        CronTrigger(hour="10-20", minute=0, timezone="Europe/Moscow"),
        kwargs={"bot": bot},
    )

    # Дневная очистка старых записей цен и алертов (в ночь на 4:00 МСК).
    scheduler.add_job(
        PriceAlertService.run_daily_cleanup,
        CronTrigger(hour=4, minute=0, timezone="Europe/Moscow"),
        kwargs={"bot": bot},
    )

    # Ежедневный пересчёт уведомлений об офертах в 06:00 МСК
    scheduler.add_job(
        OfferAlertService.schedule_daily_jobs,
        CronTrigger(hour=6, minute=0, timezone="Europe/Moscow"),
        kwargs={"bot": bot, "scheduler": scheduler},
    )

    # Еженедельная синхронизация реестра эмитентов (каталог меняется медленно).
    scheduler.add_job(
        IssuerSyncService.sync_all_issuers,
        CronTrigger(day_of_week="sun", hour=5, minute=0, timezone="Europe/Moscow"),
    )

    # Проверка обновлений рейтингов каждые 10 минут днём (08:00–22:50 МСК).
    # scheduler.add_job(
    #     NraRatingAlertService.check_rating_updates,
    #     CronTrigger(hour="8-22", minute="*/10", timezone="Europe/Moscow"),
    #     kwargs={"bot": bot},
    #     max_instances=1,
    #     coalesce=True,
    # )
    # scheduler.add_job(
    #     NkrRatingAlertService.check_rating_updates,
    #     CronTrigger(hour="8-22", minute="*/10", timezone="Europe/Moscow"),
    #     kwargs={"bot": bot},
    #     max_instances=1,
    #     coalesce=True,
    # )

    scheduler.start()

    # Восстанавливаем DateTrigger-джобы после возможного рестарта
    await OfferAlertService.schedule_daily_jobs(bot, scheduler)

    # Разовый синк реестра эмитентов на старте (в фоне, не блокирует polling).
    scheduler.add_job(IssuerSyncService.sync_all_issuers)

    # Непрерывный мониторинг блокировок ФНС (пул воркеров по прокси, окно 08:00–20:00 МСК).
    # Запуск в фоне, чтобы сборка набора не блокировала старт polling. Держим ссылки,
    # иначе сканер и его воркер-задачи может собрать GC.
    # fns_scanner = FnsScanner(bot)
    # _BACKGROUND.append(fns_scanner)
    # _BACKGROUND.append(asyncio.create_task(fns_scanner.start()))

    # Контроль выплаты купонов: календарь T-Invest × лента НРД.
    # Сервис живёт всё время процесса (держит карту держателей по ISIN).
    nsd_coupon_service = NsdCouponService(bot)
    _BACKGROUND.append(nsd_coupon_service)
    # Ежедневный синк купонного календаря подписчиков (06:30 МСК) + разово на старте.
    scheduler.add_job(
        nsd_coupon_service.sync_calendar,
        CronTrigger(hour=6, minute=30, timezone="Europe/Moscow"),
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(nsd_coupon_service.sync_calendar)
    # Сверка выплат с лентой НРД каждые 30 мин днём (09:00–22:00 МСК).
    scheduler.add_job(
        nsd_coupon_service.check_payments,
        CronTrigger(hour="9-22", minute="*/30", timezone="Europe/Moscow"),
        max_instances=1,
        coalesce=True,
    )
    # Дедлайн-проверка непоступивших купонов (22:30 МСК, после дневных сверок).
    scheduler.add_job(
        nsd_coupon_service.check_deadlines,
        CronTrigger(hour=22, minute=30, timezone="Europe/Moscow"),
        max_instances=1,
        coalesce=True,
    )
    # Ежедневный отчёт по купонам в выбранное пользователем время (минутный тик МСК).
    scheduler.add_job(
        nsd_coupon_service.send_daily_reports,
        CronTrigger(minute="*", timezone="Europe/Moscow"),
        max_instances=1,
        coalesce=True,
    )

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
