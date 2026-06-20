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
from .formatter import format_scan_report
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
# Эмитенты публикуют «О получении … выплат» заранее (наблюдали за неделю и более),
# поэтому окно широкое.
PUBLISH_LOOKBACK_DAYS = 10
# Отсрочка перед алертом после плановой даты (рабочих/календарных дней).
GRACE_DAYS = 0
# Параллельность опроса НРД в разовой проверке (страницы одного браузера).
SCAN_CONCURRENCY = 4

# Глобальный (на процесс) ограничитель тяжёлых сканов: ручной скан и фоновые
# отчёты не пересекаются, чтобы не плодить браузеры и не упираться в RPS T-Invest.
# Модульный, т.к. ручной хендлер создаёт отдельный экземпляр сервиса.
_SCAN_SEMAPHORE = asyncio.Semaphore(1)

# Круговой выбор прокси из пула — распределяем запросы НРД по разным IP, чтобы
# один адрес не упирался в троттлинг (что вызывало таймауты навигации).
_proxy_index = 0


def _pick_proxy() -> str | None:
    """Возвращает следующий прокси из пула по кругу (или ``None`` — напрямую)."""
    global _proxy_index
    proxies = load_proxies()
    proxy = proxies[_proxy_index % len(proxies)]
    _proxy_index += 1
    return proxy


# Circuit breaker: если НРД полностью недоступен, ставим живые проверки на паузу,
# чтобы ручной скан/отчёт не висели минутами (статус берётся из БД).
_NSD_COOLDOWN = timedelta(minutes=5)
_nsd_down_until: datetime | None = None


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
        # Фоновые задачи рассылки отчётов (держим ссылки от сборщика мусора).
        self._report_tasks: set[asyncio.Task[None]] = set()
        # Пользователи, чей отчёт сейчас формируется (защита от дублей).
        self._report_in_flight: set[int] = set()

    async def sync_calendar(self) -> int:
        """Загружает купонный календарь подписчиков и обновляет трекинг.

        Для каждого подписчика собирает плановые купоны из T-Invest, добавляет
        новые в трекинг и пересобирает карту держателей по ISIN.

        Returns:
            Число добавленных в трекинг купонов.

        """
        subscribers = await NsdCouponAlertSettingsRepository.list_users_with_alerts_enabled()
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

        marked = 0
        async with NsdClient(_pick_proxy()) as client:
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
                    await NsdCouponTrackingRepository.mark_paid(coupon.id, news_id, received_at)
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
        """Ищет публикацию НРД о выплате купона на дату ``coupon_date``.

        Совпадение — ``INTR`` («О получении … выплат») с плановой датой
        (``Дата КД (план.)``), равной дате купона. Сам факт такой публикации
        означает, что НРД получил средства (заполненная «Дата поступления в НРД»
        есть не у всех эмитентов, поэтому обязательной не считается).

        Returns:
            Пара (news_id, детали карточки) при совпадении, иначе ``None``.

        """
        for item in intr_items:
            if item.news_id not in card_cache:
                try:
                    card_cache[item.news_id] = parse_card(await client.fetch_card(item.news_id))
                except Exception as e:  # noqa: BLE001
                    logger.error("Карточка НРД %s не получена: %s", item.news_id, e)
                    continue
            card = card_cache[item.news_id]
            if card.planned_pay_date == coupon_date:
                return item.news_id, card
        return None

    async def scan_user(self, telegram_id: int, today: date | None = None) -> CouponScanReport:
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

        # Сериализуем тяжёлую часть (T-Invest + Playwright) на весь процесс.
        async with _SCAN_SEMAPHORE:
            plans = await collect_coupon_plans(
                telegram_id,
                date_from=datetime.combine(yesterday, time.min, tzinfo=_MSK),
                date_to=datetime.combine(today, time.max, tzinfo=_MSK),
            )
            relevant = [p for p in plans if p.coupon_date in (yesterday, today)]
            if not relevant:
                return CouponScanReport()

            # DB-first: статус известных купонов берём из трекинга (его ведёт
            # фоновый check_payments); в НРД ходим только за неподтверждёнными.
            statuses = await NsdCouponTrackingRepository.get_statuses(
                [(p.isin, p.coupon_number) for p in relevant]
            )
            scanned: list[ScannedCoupon] = []
            to_check: list[CouponPlan] = []
            for plan in relevant:
                if statuses.get((plan.isin, plan.coupon_number)) == "paid":
                    scanned.append(
                        ScannedCoupon(plan.isin, plan.bond_name, plan.coupon_date, paid=True)
                    )
                else:
                    to_check.append(plan)

            if to_check:
                scanned.extend(await self._live_check(to_check, today))

        return CouponScanReport(coupons=scanned)

    async def _live_check(
        self, plans: list[CouponPlan], today: date
    ) -> list[ScannedCoupon]:
        """Живая проверка по НРД купонов, не подтверждённых в БД.

        Защита от зависаний: если НРД недавно был полностью недоступен
        (circuit breaker активен), живую проверку пропускаем и помечаем купоны
        неподтверждёнными — без многоминутных таймаутов.
        """
        global _nsd_down_until
        now = datetime.now(UTC)
        if _nsd_down_until and now < _nsd_down_until:
            logger.warning(
                "НРД на паузе (circuit breaker), без живой проверки: %d купон(ов)",
                len(plans),
            )
            return [
                ScannedCoupon(p.isin, p.bond_name, p.coupon_date, paid=False)
                for p in plans
            ]

        by_isin: dict[str, list[CouponPlan]] = defaultdict(list)
        for plan in plans:
            by_isin[plan.isin].append(plan)
        isins = list(by_isin)

        sem = asyncio.Semaphore(SCAN_CONCURRENCY)
        async with NsdClient(_pick_proxy()) as client:
            # Первый ISIN — последовательно: проходим антибот и кэшируем cookie.
            first = await self._scan_isin(client, isins[0], by_isin, today, sem)
            rest = await asyncio.gather(
                *(self._scan_isin(client, isin, by_isin, today, sem) for isin in isins[1:])
            )
        chunks = [first, *rest]

        scanned: list[ScannedCoupon] = []
        failures = 0
        for isin, chunk in zip(isins, chunks):
            if chunk is None:  # НРД недоступен по этому ISIN (все прокси)
                failures += 1
                scanned.extend(
                    ScannedCoupon(c.isin, c.bond_name, c.coupon_date, paid=False)
                    for c in by_isin[isin]
                )
            else:
                scanned.extend(chunk)

        if failures and failures == len(isins):
            _nsd_down_until = now + _NSD_COOLDOWN
            logger.error("НРД недоступен — пауза живых проверок до %s", _nsd_down_until)
        return scanned

    async def _scan_isin(
        self,
        client: NsdClient,
        isin: str,
        by_isin: dict[str, list[CouponPlan]],
        today: date,
        sem: asyncio.Semaphore,
    ) -> list[ScannedCoupon] | None:
        """Проверяет выплаты по одному ISIN; возвращает результаты по его купонам.

        Если основной прокси не отдал страницу (таймаут/блок), повторяет ISIN
        через новый клиент на другом прокси из пула — чтобы не помечать выплату
        ложно «не найденной» из-за троттлинга одного IP.

        Returns:
            Результаты по купонам, либо ``None`` — если НРД недоступен по всем
            прокси (вызывающий учтёт это для circuit breaker).
        """
        coupons = by_isin[isin]
        async with sem:
            results = await self._scan_isin_once(client, isin, coupons, today)
            if results is not None:
                return results

            logger.warning("НРД %s: повтор на другом прокси", isin)
            async with NsdClient(_pick_proxy()) as fallback:
                results = await self._scan_isin_once(fallback, isin, coupons, today)
            if results is not None:
                return results

            logger.error("Скан НРД по %s не удался (все прокси)", isin)
            return None

    async def _scan_isin_once(
        self,
        client: NsdClient,
        isin: str,
        coupons: list[CouponPlan],
        today: date,
    ) -> list[ScannedCoupon] | None:
        """Один проход по ISIN через данный клиент.

        Returns:
            Результаты по купонам, либо ``None`` — если страница НРД не открылась
            (тогда вызывающий повторит на другом прокси).
        """
        date_from = min(c.coupon_date for c in coupons) - timedelta(days=PUBLISH_LOOKBACK_DAYS)
        try:
            html = await client.search_by_isin(
                isin, date_from=date_from, date_to=today + timedelta(days=1)
            )
        except Exception as e:  # noqa: BLE001 — сигнал вызывающему повторить
            logger.warning("НРД поиск по %s не удался: %s", isin, e)
            return None

        intr_items = [
            item
            for item in parse_listing(html)
            if item.news_type == "INTR" and item.isin == isin
        ]
        logger.info(
            "НРД скан %s: новостей найдено, INTR=%d (купонов к проверке: %d)",
            isin,
            len(intr_items),
            len(coupons),
        )
        card_cache: dict[int, NsdCardDetails] = {}
        results: list[ScannedCoupon] = []
        for coupon in coupons:
            match = await self._find_payment(client, intr_items, coupon.coupon_date, card_cache)
            logger.info(
                "НРД %s купон %s: %s",
                isin,
                coupon.coupon_date,
                "выплата подтверждена" if match else "выплата не найдена",
            )
            results.append(
                ScannedCoupon(isin, coupon.bond_name, coupon.coupon_date, paid=match is not None)
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

        logger.info("Дедлайн-проверка НРД: просрочено=%d, уведомлений=%d", len(overdue), alerted)
        return alerted

    async def send_daily_reports(self, now: datetime | None = None) -> int:
        """Рассылает ежедневный отчёт пользователям, чьё время совпало с текущим.

        Вызывается минутным тиком планировщика. Для каждого совпавшего пользователя
        собирает ту же сводку, что и ручная проверка, и шлёт её. Пропускает, если
        нет токена или за вчера/сегодня нет купонов (без ежедневного спама).

        Args:
            now: Опорный момент по МСК (по умолчанию текущий) — для тестов.

        Returns:
            Число отправленных отчётов.

        """
        now = now or datetime.now(_MSK)
        users = await NsdCouponAlertSettingsRepository.list_users_with_report_at(
            now.hour, now.minute
        )
        today = now.date()
        dispatched = 0
        for telegram_id in users:
            if telegram_id in self._report_in_flight:
                continue
            self._report_in_flight.add(telegram_id)
            task = asyncio.create_task(self._send_report_to(telegram_id, today))
            self._report_tasks.add(task)
            task.add_done_callback(self._report_tasks.discard)
            dispatched += 1

        if dispatched:
            logger.info("Ежедневные отчёты НРД: запущено задач=%d", dispatched)
        return dispatched

    async def _send_report_to(self, telegram_id: int, today: date) -> None:
        """Формирует и отправляет ежедневный отчёт одному пользователю.

        Запускается фоновой задачей. Скан сериализуется глобальным семафором,
        поэтому отчёты разных пользователей не пересекаются. Пропускает отправку,
        если нет токена или за вчера/сегодня нет купонов.
        """
        try:
            report = await self.scan_user(telegram_id, today=today)
            if report.no_token or not report.coupons:
                return
            await self._bot.send_message(
                telegram_id,
                format_scan_report(report),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            logger.info("Ежедневный отчёт по купонам отправлен %s", telegram_id)
        except Exception as e:  # noqa: BLE001 — сбой одного не валит остальных
            logger.error("Отчёт по купонам для %s не отправлен: %s", telegram_id, e)
        finally:
            self._report_in_flight.discard(telegram_id)
