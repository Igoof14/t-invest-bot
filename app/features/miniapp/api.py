"""HTTP API мини-аппа.

Тонкая обёртка над клиентами бэкенда: своей логики здесь нет, вся она осталась
в ``core/clients/backend``. Задача слоя — подставить ``telegram_id`` из
подтверждённой подписи и превратить ошибки бэкенда в понятные фронтенду коды.

``telegram_id`` всегда берётся из ``request[USER_KEY]`` и никогда из тела или
пути: иначе любой смог бы читать и менять чужие настройки.
"""

from __future__ import annotations

import asyncio
import functools
import logging
from collections.abc import Awaitable, Callable
from datetime import date, time
from typing import Any, Literal

from aiohttp import web
from common.brokers import Broker
from core.clients.backend import analytics as analytics_api
from core.clients.backend import coupons as coupons_api
from core.clients.backend import maturities as maturities_api
from core.clients.backend import notifications as notifications_api
from core.clients.backend import offers as offers_api
from core.clients.backend import users as users_api
from core.clients.backend.analytics import BondBreakdown, Cashflow
from core.clients.backend.common import PositionAccount
from core.clients.backend.coupons import CouponItem
from core.clients.backend.errors import (
    BackendError,
    InvalidToken,
    UpstreamUnavailable,
    UserNotFound,
)
from core.clients.backend.maturities import MaturityItem
from core.clients.backend.notifications import (
    DisclosureAlertSettings,
    NotificationSettings,
    OfferAlertSettings,
    PriceAlertSettings,
)
from core.clients.backend.offers import OfferItem
from core.clients.bonds_sync.client import sync_user_bonds, sync_user_events
from core.config import config
from features.analytics import EventName, track
from features.ratings.enums import AVAILABLE_AGENCIES
from pydantic import BaseModel, Field, ValidationError

from .middlewares import current_user
from .session import issue_session

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()

# Удержание фоновых задач синхронизации портфеля от сборки GC до завершения.
_SYNC_TASKS: set[asyncio.Task[None]] = set()

_Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]

# Разделы с одним тумблером. Ключи совпадают с путями бэкенда.
_TOGGLE_SECTIONS = frozenset({"offers", "prices", "fns", "disclosure"})

_AGENCY_CODES = {agency.value: agency for agency in AVAILABLE_AGENCIES}

# Сколько ближайших событий портфеля отдавать, если мини-апп не попросил иначе.
# Границы 1..50 бэкенда соблюдает сам клиент (`fetch_user_items`).
_DEFAULT_EVENTS_LIMIT = 10

RiskLevel = Literal["low", "medium", "high", "critical"]


def handle_backend_errors(handler: _Handler) -> _Handler:
    """Превращает ошибки клиента бэкенда в ответы API.

    Наружу уходит только статус и короткое сообщение: детали приватного сервиса
    фронтенду не нужны и не должны утекать в браузер.
    """

    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)
        except UserNotFound:
            return web.json_response({"error": "пользователь не найден"}, status=404)
        except InvalidToken:
            # Единственная ошибка, которую чинит сам пользователь, — про неё
            # фронтенду нужно сказать прямо, а не общим «сервис недоступен».
            return web.json_response({"error": "Брокер отверг токен"}, status=400)
        except UpstreamUnavailable:
            return web.json_response({"error": "Брокер не отвечает"}, status=503)
        except BackendError as e:
            logger.error("Ошибка бэкенда в запросе мини-аппа %s: %s", request.path, e)
            return web.json_response({"error": "сервис временно недоступен"}, status=502)

    return wrapper


class OffersPatch(BaseModel):
    """Изменение настроек напоминаний об оферте. Диапазоны — как у бэкенда."""

    first_alert: int | None = Field(default=None, ge=1, le=365)
    second_alert: int | None = Field(default=None, ge=1, le=365)
    notification_time: time | None = None


class PricesPatch(BaseModel):
    """Изменение порогов уведомлений о цене, в процентах."""

    drop_warning_threshold: float | None = Field(default=None, gt=0, lt=100)
    drop_critical_threshold: float | None = Field(default=None, gt=0, lt=100)
    rise_warning_threshold: float | None = Field(default=None, gt=0, lt=100)
    rise_critical_threshold: float | None = Field(default=None, gt=0, lt=100)


class DisclosurePatch(BaseModel):
    """Изменение порога риска раскрытий."""

    min_risk_level: RiskLevel | None = None


class TokenPayload(BaseModel):
    """Токен брокера, только на чтение."""

    token: str = Field(min_length=1, max_length=2048)


async def _validated(request: web.Request, model: type[BaseModel]) -> Any:
    """Разбирает тело запроса моделью.

    Raises:
        web.HTTPBadRequest: Тело не JSON или не проходит валидацию.

    """
    try:
        body = await request.json()
    except ValueError:
        raise web.HTTPBadRequest(reason="invalid json") from None
    try:
        return model.model_validate(body)
    except ValidationError as e:
        logger.info("Невалидное тело запроса мини-аппа %s: %s", request.path, e)
        raise web.HTTPBadRequest(reason="invalid body") from None


def _offers_payload(settings: OfferAlertSettings) -> dict[str, Any]:
    return {
        "alerts_enabled": settings.alerts_enabled,
        "first_alert": settings.first_alert,
        "second_alert": settings.second_alert,
        "notification_time": settings.notification_time.isoformat(),
    }


def _prices_payload(settings: PriceAlertSettings) -> dict[str, Any]:
    return {
        "alerts_enabled": settings.alerts_enabled,
        "drop_warning_threshold": settings.drop_warning_threshold,
        "drop_critical_threshold": settings.drop_critical_threshold,
        "rise_warning_threshold": settings.rise_warning_threshold,
        "rise_critical_threshold": settings.rise_critical_threshold,
    }


def _disclosure_payload(settings: DisclosureAlertSettings) -> dict[str, Any]:
    return {
        "alerts_enabled": settings.alerts_enabled,
        "min_risk_level": settings.min_risk_level,
    }


def _settings_payload(settings: NotificationSettings) -> dict[str, Any]:
    """Состояние всех разделов в форме, которую ждёт мини-апп."""
    return {
        "offers": _offers_payload(settings.offers),
        "prices": _prices_payload(settings.prices),
        "ratings": {"enabled_agencies": sorted(settings.enabled_agencies)},
        "fns": {"alerts_enabled": settings.fns_enabled},
        "disclosure": _disclosure_payload(settings.disclosure),
    }


def _events_limit(request: web.Request) -> int:
    """Сколько ближайших событий запросить у бэкенда.

    Мусор в query не повод отказывать: подставляем значение по умолчанию, а
    границы 1..50 всё равно зажимает клиент бэкенда.
    """
    try:
        return int(request.query["limit"])
    except (KeyError, ValueError):
        return _DEFAULT_EVENTS_LIMIT


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _account_payload(account: PositionAccount) -> dict[str, Any]:
    return {
        "broker": account.broker,
        "account_id": account.account_id,
        "account_name": account.account_name,
        "quantity": account.quantity,
    }


def _bond_payload(item: OfferItem | MaturityItem | CouponItem) -> dict[str, Any]:
    """Общая часть события портфеля — сама облигация и позиция по ней."""
    return {
        "secid": item.secid,
        "isin": item.isin,
        "shortname": item.shortname,
        "name": item.name,
        "facevalue": item.facevalue,
        "faceunit": item.faceunit,
        "maturity_date": _iso(item.maturity_date),
        "quantity": item.quantity,
        "accounts": [_account_payload(account) for account in item.accounts],
        "moex_link": item.moex_link,
    }


def _offer_payload(item: OfferItem) -> dict[str, Any]:
    """Оферта в плоской форме: вложенность бэкенда фронтенду не нужна."""
    return {
        **_bond_payload(item),
        "days_left": item.days_left,
        "offer_date": _iso(item.offer_date),
        "offer_type": item.offer_type,
        "date_start": _iso(item.date_start),
        "date_end": _iso(item.date_end),
        "price": item.price,
        "value": item.value,
        "agent": item.agent,
    }


def _maturity_payload(item: MaturityItem) -> dict[str, Any]:
    return {**_bond_payload(item), "days_left": item.days_left}


def _coupon_payload(item: CouponItem) -> dict[str, Any]:
    """Купон в плоской форме.

    ``days_left`` тут всегда ``None``: все купоны ответа платят в один день, и
    считать до него нечего — поле остаётся ради общей формы события портфеля.
    """
    return {
        **_bond_payload(item),
        "days_left": None,
        "coupon_date": _iso(item.coupon_date),
        "coupon_start_date": _iso(item.coupon_start_date),
        "coupon_value": item.coupon_value,
        "total_value": item.total_value,
        "is_disclosure": item.is_disclosure,
        "disclosure": (
            None
            if item.disclosure is None
            else {
                "total_payment_amount": item.disclosure.total_payment_amount,
                "payment_per_security_value": item.disclosure.payment_per_security_value,
                "event_url": item.disclosure.event_url,
            }
        ),
        "nsd": {"is_paid": item.nsd.is_paid, "url": item.nsd.url},
    }


def _coupons_date(request: web.Request) -> date | None:
    """Дата выплаты из query.

    Мусор в параметре не повод отказывать: ``None`` означает «сегодня», и это
    ровно то, что нужно экрану по умолчанию.
    """
    try:
        return date.fromisoformat(request.query["date"])
    except (KeyError, ValueError):
        return None


def _analytics_range(request: web.Request) -> tuple[date | None, date | None]:
    """Границы диапазона из query.

    Мусор в параметре не повод отказывать: ``None`` означает «пусть решает
    бэкенд», а он подставляет первую операцию пользователя и сегодняшний день.
    """
    return _query_date(request, "date_from"), _query_date(request, "date_to")


def _query_date(request: web.Request, name: str) -> date | None:
    try:
        return date.fromisoformat(request.query[name])
    except (KeyError, ValueError):
        return None


def _granularity(request: web.Request) -> str:
    """Гранулярность колонок. Неизвестное значение — как будто его не просили."""
    value = request.query.get("granularity", analytics_api.DEFAULT_GRANULARITY)
    return value if value in analytics_api.GRANULARITIES else analytics_api.DEFAULT_GRANULARITY


def _bonds_limit(request: web.Request) -> int:
    try:
        return int(request.query["limit"])
    except (KeyError, ValueError):
        return analytics_api.DEFAULT_BONDS_LIMIT


def _cashflow_payload(report: Cashflow) -> dict[str, Any]:
    """Метрики уезжают списком, а не полями: их состав задаёт бэкенд."""
    return {
        "granularity": report.granularity,
        "date_from": _iso(report.date_from),
        "date_to": _iso(report.date_to),
        "periods": [
            {
                "key": period.key,
                "label": period.label,
                "start": _iso(period.start),
                "end": _iso(period.end),
            }
            for period in report.periods
        ],
        "metrics": [
            {
                "key": series.key,
                "label": series.label,
                "sign": series.sign,
                "values": series.values,
                "total": series.total,
            }
            for series in report.metrics
        ],
    }


def _bonds_payload(report: BondBreakdown) -> dict[str, Any]:
    return {
        "date_from": _iso(report.date_from),
        "date_to": _iso(report.date_to),
        "columns": [
            {"key": column.key, "label": column.label, "sign": column.sign}
            for column in report.columns
        ],
        "items": [
            {
                "isin": row.isin,
                "ticker": row.ticker,
                "name": row.name,
                "events": row.events,
                "values": row.values,
            }
            for row in report.items
        ],
    }


@routes.post("/miniapp/api/session")
async def create_session(request: web.Request) -> web.Response:
    """Меняет подпись Telegram на сессию — и продлевает уже выданную.

    Продление по действующей сессии разрешено намеренно. Telegram обновляет
    ``initData`` только при запуске страницы, а мини-апп при закрытии не
    выгружается: требуя свежую подпись раз в месяц, мы вернули бы ровно ту
    поломку, ради которой сессии и заведены. Плата — скользящий срок жизни;
    отозвать все сессии можно ротацией токена бота.
    """
    token, expires_at = issue_session(current_user(request), config.bot_token.get_secret_value())
    return web.json_response({"token": token, "expires_at": expires_at})


async def _broker_tokens(telegram_id: int) -> list[dict[str, Any]]:
    """Статус токена по каждому известному брокеру.

    Бэкенд хранит токены по отдельности на брокера и не отдаёт агрегат одним
    запросом, поэтому читаем каждый параллельно — иначе профиль ждал бы три
    последовательных round-trip'а.
    """
    tokens = await asyncio.gather(*(users_api.get_token(telegram_id, broker) for broker in Broker))
    return [
        {"broker": broker.value, "has_token": token is not None}
        for broker, token in zip(Broker, tokens, strict=True)
    ]


@routes.get("/miniapp/api/me")
@handle_backend_errors
async def get_me(request: web.Request) -> web.Response:
    """Профиль пользователя и статус токена по каждому брокеру.

    Заодно регистрирует пользователя: мини-апп можно открыть из ссылки, ни разу
    не нажав `/start`, и без этого бэкенд не знал бы о нём.
    """
    user = current_user(request)
    _registration, tokens = await asyncio.gather(
        users_api.register(
            user.telegram_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
        ),
        _broker_tokens(user.telegram_id),
    )
    return web.json_response(
        {
            "telegram_id": user.telegram_id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "tokens": tokens,
        }
    )


@routes.get("/miniapp/api/offers")
@handle_backend_errors
async def get_offers(request: web.Request) -> web.Response:
    """Ближайшие оферты по облигациям из портфеля пользователя."""
    items = await offers_api.get_offers(current_user(request).telegram_id, _events_limit(request))
    return web.json_response([_offer_payload(item) for item in items])


@routes.get("/miniapp/api/maturities")
@handle_backend_errors
async def get_maturities(request: web.Request) -> web.Response:
    """Ближайшие погашения облигаций из портфеля пользователя."""
    items = await maturities_api.get_maturities(
        current_user(request).telegram_id, _events_limit(request)
    )
    return web.json_response([_maturity_payload(item) for item in items])


@routes.get("/miniapp/api/coupons")
@handle_backend_errors
async def get_coupons(request: web.Request) -> web.Response:
    """Купоны по портфелю пользователя, выплачиваемые в запрошенный день.

    Список не режется `limit`: в один день выплат немного, и обрезать его
    значило бы скрыть от пользователя часть сегодняшних денег.
    """
    payments = await coupons_api.get_coupons(
        current_user(request).telegram_id, _coupons_date(request)
    )
    return web.json_response(
        {
            "date": _iso(payments.date),
            "items": [_coupon_payload(item) for item in payments.items],
        }
    )


@routes.get("/miniapp/api/analytics/cashflow")
@handle_backend_errors
async def get_analytics_cashflow(request: web.Request) -> web.Response:
    """Денежный поток по облигациям пользователя, разложенный по периодам."""
    date_from, date_to = _analytics_range(request)
    report = await analytics_api.get_cashflow(
        current_user(request).telegram_id, _granularity(request), date_from, date_to
    )
    return web.json_response(_cashflow_payload(report))


@routes.get("/miniapp/api/analytics/bonds")
@handle_backend_errors
async def get_analytics_bonds(request: web.Request) -> web.Response:
    """Те же метрики в разрезе бумаг, по убыванию чистого потока."""
    date_from, date_to = _analytics_range(request)
    report = await analytics_api.get_bond_breakdown(
        current_user(request).telegram_id, date_from, date_to, _bonds_limit(request)
    )
    return web.json_response(_bonds_payload(report))


@routes.get("/miniapp/api/notifications")
@handle_backend_errors
async def get_notifications(request: web.Request) -> web.Response:
    """Состояние всех разделов уведомлений одним ответом."""
    settings = await notifications_api.get_settings(current_user(request).telegram_id)
    return web.json_response(_settings_payload(settings))


@routes.post("/miniapp/api/notifications/{section}/toggle")
@handle_backend_errors
async def toggle_section(request: web.Request) -> web.Response:
    """Переключает раздел с одним тумблером."""
    section = request.match_info["section"]
    if section not in _TOGGLE_SECTIONS:
        return web.json_response({"error": "неизвестный раздел"}, status=404)

    enabled = await notifications_api.toggle(current_user(request).telegram_id, section)
    return web.json_response({"alerts_enabled": enabled})


@routes.post("/miniapp/api/notifications/ratings/{agency}/toggle")
@handle_backend_errors
async def toggle_agency(request: web.Request) -> web.Response:
    """Переключает подписку на рейтинговое агентство."""
    agency = request.match_info["agency"]
    # Набор агентств задаёт бот: неизвестный код дальше не пускаем, чтобы в
    # бэкенде не оседали подписки на несуществующие агентства.
    if agency not in _AGENCY_CODES:
        return web.json_response({"error": "неизвестное агентство"}, status=404)

    enabled = await notifications_api.toggle_agency(current_user(request).telegram_id, agency)
    return web.json_response({"alerts_enabled": enabled})


@routes.patch("/miniapp/api/notifications/offers")
@handle_backend_errors
async def update_offers(request: web.Request) -> web.Response:
    """Меняет сроки и время напоминаний об оферте."""
    patch: OffersPatch = await _validated(request, OffersPatch)
    settings = await notifications_api.update_offers(
        current_user(request).telegram_id, **patch.model_dump(exclude_none=True)
    )
    return web.json_response(_offers_payload(settings))


@routes.patch("/miniapp/api/notifications/prices")
@handle_backend_errors
async def update_prices(request: web.Request) -> web.Response:
    """Меняет пороги уведомлений о цене."""
    patch: PricesPatch = await _validated(request, PricesPatch)
    settings = await notifications_api.update_prices(
        current_user(request).telegram_id, **patch.model_dump(exclude_none=True)
    )
    return web.json_response(_prices_payload(settings))


@routes.patch("/miniapp/api/notifications/disclosure")
@handle_backend_errors
async def update_disclosure(request: web.Request) -> web.Response:
    """Меняет минимальный уровень риска раскрытий."""
    patch: DisclosurePatch = await _validated(request, DisclosurePatch)
    settings = await notifications_api.update_disclosure(
        current_user(request).telegram_id, **patch.model_dump(exclude_none=True)
    )
    return web.json_response(_disclosure_payload(settings))


@routes.get("/miniapp/api/ratings/agencies")
async def list_agencies(_: web.Request) -> web.Response:
    """Агентства, по которым бот умеет присылать уведомления.

    Список отдаёт сервер, а не хардкодит фронтенд: он растёт вместе со
    скрейперами (``features/ratings/enums.py``).
    """
    return web.json_response(
        [{"code": agency.value, "name": agency.display_name} for agency in AVAILABLE_AGENCIES]
    )


def _broker(request: web.Request) -> Broker | None:
    """Брокер из пути, или None — если код неизвестен."""
    try:
        return Broker(request.match_info["broker"])
    except ValueError:
        return None


async def _sync_portfolio(telegram_id: int) -> None:
    """Синхронизирует портфель после подключения токена.

    Сначала список облигаций, затем историю операций — она привязана к уже
    сохранённым бумагам. В отличие от старого бот-флоу здесь некому сообщить
    результат: фронтенд узнаёт о нём через собственный опрос данных, а не
    через сообщение в чат.
    """
    bonds_synced = await sync_user_bonds(telegram_id)
    await track(
        EventName.BONDS_SYNCED,
        telegram_id=telegram_id,
        count=bonds_synced,
        ok=bonds_synced is not None,
    )

    events_synced = await sync_user_events(telegram_id)
    await track(
        EventName.EVENTS_SYNCED,
        telegram_id=telegram_id,
        count=events_synced,
        ok=events_synced is not None,
    )


def _schedule_portfolio_sync(telegram_id: int) -> None:
    task = asyncio.create_task(_sync_portfolio(telegram_id))
    _SYNC_TASKS.add(task)
    task.add_done_callback(_SYNC_TASKS.discard)


@routes.put("/miniapp/api/tokens/{broker}")
@handle_backend_errors
async def set_token(request: web.Request) -> web.Response:
    """Подключает токен указанного брокера и запускает синхронизацию портфеля."""
    broker = _broker(request)
    if broker is None:
        return web.json_response({"error": "неизвестный брокер"}, status=404)

    payload: TokenPayload = await _validated(request, TokenPayload)
    telegram_id = current_user(request).telegram_id
    await users_api.set_token(telegram_id, broker, payload.token)
    _schedule_portfolio_sync(telegram_id)
    return web.json_response({"has_token": True})


@routes.delete("/miniapp/api/tokens/{broker}")
@handle_backend_errors
async def delete_token(request: web.Request) -> web.Response:
    """Отвязывает токен указанного брокера."""
    broker = _broker(request)
    if broker is None:
        return web.json_response({"error": "неизвестный брокер"}, status=404)

    await users_api.delete_token(current_user(request).telegram_id, broker)
    return web.json_response({"has_token": False})
