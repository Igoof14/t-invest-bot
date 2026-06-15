"""Непрерывный пул воркеров мониторинга блокировок ФНС.

Каждый воркер закреплён за своим прокси и берёт ИНН из общей круговой очереди.
Работает только в дневном окне по МСК. Проверенный ИНН возвращается в конец
очереди; ИНН с нерешённой капчей — тоже (его подхватит другой воркер/прокси).
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot
from features.issuers.models import Issuer
from features.issuers.repository import IssuerRepository

from .client import run
from .events import parse_rows
from .notifier import FnsBlockNotifier
from .pipeline import collect_holdings, match_alerts, resolve_block
from .proxy_pool import load_proxies
from .repository import FnsAlertSettingsRepository, FnsBlockingRepository

logger = logging.getLogger(__name__)

_MSK = ZoneInfo("Europe/Moscow")

# Рабочее окно по МСК: будни (Пн–Пт), [08:00, 20:00).
WINDOW_START_HOUR = 8
WINDOW_END_HOUR = 20
# Пересборка рабочего набора ИНН (подхват новых подписчиков/портфелей).
REFRESH_INTERVAL = 900  # 15 мин
# Минимальный интервал между перепроверками одного ИНН (защита от трат 2captcha).
MIN_REVISIT_SECONDS = 1800  # 30 мин
# Число попыток решения капчи на один ИНН.
RETRIES = 3
# Пауза воркера, когда очередь пуста или все ИНН недавно проверены.
IDLE_SLEEP = 15
# Максимальная пауза при ожидании открытия окна (чтобы периодически пересматривать).
WINDOW_SLEEP_CAP = 600


def in_window(now: datetime) -> bool:
    """Возвращает, попадает ли момент в рабочее окно по МСК (Пн–Пт, [08:00, 20:00))."""
    return now.weekday() < 5 and WINDOW_START_HOUR <= now.hour < WINDOW_END_HOUR


def seconds_until_open(now: datetime) -> float:
    """Возвращает число секунд до открытия окна (0, если оно уже открыто).

    Выходные пропускаются — ближайшее открытие переносится на понедельник.
    """
    if in_window(now):
        return 0.0
    candidate = now.replace(hour=WINDOW_START_HOUR, minute=0, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    while candidate.weekday() >= 5:  # пропускаем Сб/Вс
        candidate += timedelta(days=1)
    return (candidate - now).total_seconds()


def should_skip_revisit(
    inn: str, now: datetime, last_checked: dict[str, datetime]
) -> bool:
    """Возвращает, проверялся ли ИНН недавно (раньше ``MIN_REVISIT_SECONDS``)."""
    previous = last_checked.get(inn)
    if previous is None:
        return False
    return (now - previous).total_seconds() < MIN_REVISIT_SECONDS


class FnsScanner:
    """Пул воркеров: круговое сканирование ИНН подписчиков по пулу прокси."""

    def __init__(self, bot: Bot) -> None:
        """Собирает сканер."""
        self._notifier = FnsBlockNotifier(bot)
        self._proxies = load_proxies()
        self._queue: deque[str] = deque()
        self._skip: set[str] = set()
        self._last_checked: dict[str, datetime] = {}
        self._held_by_user: dict[int, set[str]] = {}
        self._issuer_by_inn: dict[str, Issuer] = {}
        self._tasks: list[asyncio.Task[None]] = []

    async def start(self) -> None:
        """Строит рабочий набор и запускает воркеры и периодический рефреш."""
        await self._build_context()
        self._tasks.append(asyncio.create_task(self._refresh_loop()))
        for proxy in self._proxies:
            self._tasks.append(asyncio.create_task(self._worker(proxy)))
        logger.info(
            "FNS-сканер запущен: воркеров=%d, ИНН в очереди=%d",
            len(self._proxies),
            len(self._queue),
        )

    async def _build_context(self) -> None:
        """Пересобирает рабочий набор ИНН и карты подписчиков/эмитентов."""
        subscribers = await FnsAlertSettingsRepository.list_users_with_alerts_enabled()
        if not subscribers:
            self._held_by_user = {}
            self._issuer_by_inn = {}
            self._queue.clear()
            logger.info("FNS-сканер: подписчиков нет, очередь пуста")
            return

        held_by_user = await collect_holdings(subscribers)
        all_held: set[str] = set().union(*held_by_user.values()) if held_by_user else set()

        issuers = await IssuerRepository.get_issuers_by_identifiers(all_held)
        issuer_by_inn = {issuer.inn: issuer for issuer in issuers if issuer.inn}

        self._held_by_user = held_by_user
        self._issuer_by_inn = issuer_by_inn

        self._queue.clear()
        for inn in issuer_by_inn:
            if inn not in self._skip:
                self._queue.append(inn)

        logger.info(
            "FNS-сканер: рабочий набор обновлён — подписчиков=%d, ИНН=%d",
            len(held_by_user),
            len(self._queue),
        )

    async def _refresh_loop(self) -> None:
        """Периодически пересобирает рабочий набор."""
        while True:
            await asyncio.sleep(REFRESH_INTERVAL)
            try:
                await self._build_context()
            except Exception as e:
                logger.error(f"FNS-сканер: ошибка обновления набора: {e}")

    async def _worker(self, proxy: str | None) -> None:
        """Цикл воркера: окно → взять ИНН → проверить → вернуть в очередь."""
        while True:
            now = datetime.now(_MSK)
            if not in_window(now):
                await asyncio.sleep(min(seconds_until_open(now), WINDOW_SLEEP_CAP))
                continue

            try:
                inn = self._queue.popleft()
            except IndexError:
                await asyncio.sleep(IDLE_SLEEP)
                continue

            if should_skip_revisit(inn, datetime.now(_MSK), self._last_checked):
                self._queue.append(inn)
                await asyncio.sleep(IDLE_SLEEP)
                continue

            await self._process(inn, proxy)

    async def _process(self, inn: str, proxy: str | None) -> None:
        """Проверяет один ИНН и решает его судьбу в очереди."""
        try:
            result = await run(inn, retries=RETRIES, proxy=proxy)
        except ValueError as e:
            # Битый ИНН — больше не проверяем.
            logger.info(f"ИНН {inn} исключён: {e}")
            self._skip.add(inn)
            return
        except Exception as e:
            # Капча не решена / сетевая ошибка — вернуть в очередь (другой прокси).
            logger.warning(f"ИНН {inn} не проверен, в очередь: {e}")
            self._queue.append(inn)
            return

        self._last_checked[inn] = datetime.now(_MSK)
        try:
            await self._check_and_notify(inn, result)
        except Exception as e:
            logger.error(f"ИНН {inn}: ошибка обработки результата: {e}")
        self._queue.append(inn)

    async def _check_and_notify(self, inn: str, result: dict) -> None:
        """Дедуп блокировок ИНН и рассылка держателям по новым блокировкам."""
        orders = parse_rows(inn, result)
        had_history = await FnsBlockingRepository.has_any(inn)
        new_orders = await FnsBlockingRepository.sync(inn, orders)

        if not had_history:
            logger.info(
                f"ИНН {inn}: первичная фиксация ({len(orders)} блокировок), "
                "без уведомления"
            )
            return

        if not new_orders:
            return

        issuer = self._issuer_by_inn.get(inn)
        if issuer is None:
            return

        block = await resolve_block(issuer, new_orders)
        if not block.identifiers:
            return

        for telegram_id, held in self._held_by_user.items():
            alerts = match_alerts(held, [block])
            if not alerts:
                continue
            try:
                await self._notifier.send(telegram_id, alerts)
            except Exception as e:
                logger.error(f"Ошибка при уведомлении {telegram_id}: {e}")
