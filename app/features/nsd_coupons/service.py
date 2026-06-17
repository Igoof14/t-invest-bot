"""Сервис мониторинга купонов: синк календаря, проверка выплат и дедлайнов."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot
from features.users.repository import BotUserRepository

from .client import NsdClient
from .models import NsdCouponTracking
from .notifier import NsdCouponNotifier
from .parser import parse_card, parse_listing
from .proxy_pool import load_proxies
from .repository import NsdCouponAlertSettingsRepository, NsdCouponTrackingRepository
from .schemas import (
    CouponMissAlert,
    CouponPlan,
    CouponScanReport,
    NsdCardDetails,
    NsdNewsItem,
    ScannedCoupon,
)
from .t_invest import collect_coupon_plans

logger = logging.getLogger(__name__)

_MSK = ZoneInfo("Europe/Moscow")

# Насколько вперёд проверять купоны (ловим досрочные публикации НРД).
PAYMENT_LOOKAHEAD_DAYS = 3
# Насколько назад от даты купона искать публикацию в ленте НРД.
PUBLISH_LOOKBACK_DAYS = 7
# Отсрочка перед алертом после плановой даты (рабочих/календарных дней).
GRACE_DAYS = 0
# Параллельность опроса НРД в разовой проверке (страницы одного браузера).
SCAN_CONCURRENCY = 4


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
        self._notifier = NsdCouponNotifier(bot)
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

    async def check_payments(self, today: date | None = None) -> int:
        """Сверяет ожидаемые купоны с публикациями НРД и помечает выплаченные.

        Для каждого ISIN с купонами на подходе запрашивает ленту НРД и ищет
        публикацию о выплате (``INTR``) с совпадающей плановой датой и заполненной
        датой поступления средств в НРД.

        Args:
            today: Опорная дата (по умолчанию сегодня) — для тестов.

        Returns:
            Число купонов, помеченных выплаченными.
        """
        today = today or datetime.now(UTC).date()
        due = await NsdCouponTrackingRepository.list_pending_due(
            today + timedelta(days=PAYMENT_LOOKAHEAD_DAYS)
        )
        if not due:
            return 0

        by_isin: dict[str, list[NsdCouponTracking]] = defaultdict(list)
        for coupon in due:
            by_isin[coupon.isin].append(coupon)

        proxies = load_proxies()
        marked = 0
        async with NsdClient(proxies[0]) as client:
            for isin, coupons in by_isin.items():
                date_from = min(c.coupon_date for c in coupons) - timedelta(
                    days=PUBLISH_LOOKBACK_DAYS
                )
                try:
                    html = await client.search_by_isin(
                        isin, date_from=date_from, date_to=today + timedelta(days=1)
                    )
                except Exception as e:  # noqa: BLE001 — сбой по бумаге не валит проход
                    logger.error("Опрос НРД по %s не удался: %s", isin, e)
                    continue

                intr_items = [
                    item
                    for item in parse_listing(html)
                    if item.news_type == "INTR" and item.isin == isin
                ]
                card_cache: dict[int, NsdCardDetails] = {}
                for coupon in coupons:
                    match = await self._find_payment(
                        client, intr_items, coupon.coupon_date, card_cache
                    )
                    if match is None:
                        continue
                    news_id, card = match
                    received_at = (
                        datetime.combine(card.nsd_received_date, time.min, tzinfo=UTC)
                        if card.nsd_received_date
                        else None
                    )
                    await NsdCouponTrackingRepository.mark_paid(
                        coupon.id, news_id, received_at
                    )
                    marked += 1

        logger.info("Проверка выплат НРД: проверено=%d, выплачено=%d", len(due), marked)
        return marked

    async def _find_payment(
        self,
        client: NsdClient,
        intr_items: list[NsdNewsItem],
        coupon_date: date,
        card_cache: dict[int, NsdCardDetails],
    ) -> tuple[int, NsdCardDetails] | None:
        """Ищет публикацию НРД, подтверждающую выплату купона на дату ``coupon_date``.

        Совпадение — ``INTR`` с плановой датой, равной дате купона, и заполненной
        датой поступления средств в НРД.

        Returns:
            Пара (news_id, детали карточки) при совпадении, иначе ``None``.
        """
        for item in intr_items:
            if item.news_id not in card_cache:
                try:
                    card_cache[item.news_id] = parse_card(
                        await client.fetch_card(item.news_id)
                    )
                except Exception as e:  # noqa: BLE001
                    logger.error("Карточка НРД %s не получена: %s", item.news_id, e)
                    continue
            card = card_cache[item.news_id]
            if (
                card.planned_pay_date == coupon_date
                and card.nsd_received_date is not None
            ):
                return item.news_id, card
        return None

    async def scan_user(
        self, telegram_id: int, today: date | None = None
    ) -> CouponScanReport:
        """Разово проверяет купоны пользователя за вчера и сегодня по ленте НРД.

        Read-only: берёт купоны портфеля за период, опрашивает НРД по каждому ISIN
        параллельно и отмечает, подтверждена ли выплата.

        Args:
            telegram_id: Telegram ID пользователя.
            today: Опорная дата (по умолчанию сегодня по МСК) — для тестов.

        Returns:
            Отчёт ``CouponScanReport`` для показа пользователю.
        """
        today = today or datetime.now(_MSK).date()
        yesterday = today - timedelta(days=1)

        token = await BotUserRepository.get_token_by_telegram_id(telegram_id)
        if not token:
            return CouponScanReport(no_token=True)

        plans = await collect_coupon_plans(
            telegram_id,
            date_from=datetime.combine(yesterday, time.min, tzinfo=_MSK),
            date_to=datetime.combine(today, time.max, tzinfo=_MSK),
        )
        relevant = [p for p in plans if p.coupon_date in (yesterday, today)]
        if not relevant:
            return CouponScanReport()

        by_isin: dict[str, list[CouponPlan]] = defaultdict(list)
        for plan in relevant:
            by_isin[plan.isin].append(plan)

        proxies = load_proxies()
        sem = asyncio.Semaphore(SCAN_CONCURRENCY)
        scanned: list[ScannedCoupon] = []
        async with NsdClient(proxies[0]) as client:
            isins = list(by_isin)
            # Первый ISIN — последовательно: проходим антибот и кэшируем cookie.
            scanned.extend(await self._scan_isin(client, isins[0], by_isin, today, sem))
            rest = await asyncio.gather(
                *(self._scan_isin(client, isin, by_isin, today, sem) for isin in isins[1:])
            )
            for chunk in rest:
                scanned.extend(chunk)

        return CouponScanReport(coupons=scanned)

    async def _scan_isin(
        self,
        client: NsdClient,
        isin: str,
        by_isin: dict[str, list[CouponPlan]],
        today: date,
        sem: asyncio.Semaphore,
    ) -> list[ScannedCoupon]:
        """Проверяет выплаты по одному ISIN; возвращает результаты по его купонам."""
        coupons = by_isin[isin]
        async with sem:
            date_from = min(c.coupon_date for c in coupons) - timedelta(
                days=PUBLISH_LOOKBACK_DAYS
            )
            try:
                html = await client.search_by_isin(
                    isin, date_from=date_from, date_to=today + timedelta(days=1)
                )
            except Exception as e:  # noqa: BLE001 — сбой по бумаге не валит весь скан
                logger.error("Скан НРД по %s не удался: %s", isin, e)
                return [
                    ScannedCoupon(isin, c.bond_name, c.coupon_date, paid=False)
                    for c in coupons
                ]

            intr_items = [
                item
                for item in parse_listing(html)
                if item.news_type == "INTR" and item.isin == isin
            ]
            card_cache: dict[int, NsdCardDetails] = {}
            results: list[ScannedCoupon] = []
            for coupon in coupons:
                match = await self._find_payment(
                    client, intr_items, coupon.coupon_date, card_cache
                )
                results.append(
                    ScannedCoupon(
                        isin, coupon.bond_name, coupon.coupon_date, paid=match is not None
                    )
                )
            return results

    async def check_deadlines(self, today: date | None = None) -> int:
        """Уведомляет о купонах, не подтверждённых выплатой к дедлайну.

        Ожидаемые купоны, чья плановая дата прошла более чем на ``GRACE_DAYS``
        и которые всё ещё в статусе ``pending`` (НРД не опубликовал выплату),
        считаются непоступившими: уведомляем держателей и помечаем ``alerted``.

        Args:
            today: Опорная дата (по умолчанию сегодня) — для тестов.

        Returns:
            Число купонов, по которым разосланы уведомления.
        """
        today = today or datetime.now(UTC).date()
        deadline = today - timedelta(days=GRACE_DAYS)
        overdue = await NsdCouponTrackingRepository.list_pending_due(deadline)
        if not overdue:
            return 0

        alerted = 0
        for coupon in overdue:
            holders = self._holders_by_isin.get(coupon.isin, set())
            alert = CouponMissAlert(
                isin=coupon.isin,
                bond_name=coupon.bond_name,
                issuer_name=coupon.issuer_name,
                coupon_number=coupon.coupon_number,
                coupon_date=coupon.coupon_date,
                amount=coupon.amount,
            )
            for telegram_id in holders:
                await self._notifier.send(telegram_id, alert)
            if holders:
                alerted += 1
            else:
                logger.warning(
                    "Купон %s №%d просрочен, но держателей в кэше нет",
                    coupon.isin,
                    coupon.coupon_number,
                )
            await NsdCouponTrackingRepository.mark_alerted(coupon.id)

        logger.info(
            "Дедлайн-проверка НРД: просрочено=%d, уведомлений=%d", len(overdue), alerted
        )
        return alerted
