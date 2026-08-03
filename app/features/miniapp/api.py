"""HTTP API мини-аппа.

Тонкая обёртка над клиентами бэкенда: своей логики здесь нет, вся она осталась
в ``core/clients/backend``. Задача слоя — подставить ``telegram_id`` из
подтверждённой подписи и превратить ошибки бэкенда в понятные фронтенду коды.

``telegram_id`` всегда берётся из ``request[USER_KEY]`` и никогда из тела или
пути: иначе любой смог бы читать и менять чужие настройки.
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Awaitable, Callable
from datetime import time
from typing import Any, Literal

from aiohttp import web
from core.clients.backend import notifications as notifications_api
from core.clients.backend import users as users_api
from core.clients.backend.errors import BackendError, UserNotFound
from core.clients.backend.notifications import (
    DisclosureAlertSettings,
    NotificationSettings,
    OfferAlertSettings,
    PriceAlertSettings,
)
from core.config import config
from features.ratings.enums import AVAILABLE_AGENCIES
from pydantic import BaseModel, Field, ValidationError

from .middlewares import current_user
from .session import issue_session

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()

_Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]

# Разделы с одним тумблером. Ключи совпадают с путями бэкенда.
_TOGGLE_SECTIONS = frozenset({"offers", "prices", "fns", "disclosure"})

_AGENCY_CODES = {agency.value: agency for agency in AVAILABLE_AGENCIES}

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
    """Токен Т-Инвестиций, только на чтение."""

    token: str = Field(min_length=1, max_length=255)


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


@routes.get("/miniapp/api/me")
@handle_backend_errors
async def get_me(request: web.Request) -> web.Response:
    """Профиль пользователя и статус токена.

    Заодно регистрирует пользователя: мини-апп можно открыть из ссылки, ни разу
    не нажав `/start`, и без этого бэкенд не знал бы о нём.
    """
    user = current_user(request)
    registration = await users_api.register(
        user.telegram_id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )
    return web.json_response(
        {
            "telegram_id": user.telegram_id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "has_token": registration.has_token,
        }
    )


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


@routes.put("/miniapp/api/token")
@handle_backend_errors
async def set_token(request: web.Request) -> web.Response:
    """Подключает токен Т-Инвестиций."""
    payload: TokenPayload = await _validated(request, TokenPayload)
    await users_api.set_token(current_user(request).telegram_id, payload.token)
    return web.json_response({"has_token": True})


@routes.delete("/miniapp/api/token")
@handle_backend_errors
async def delete_token(request: web.Request) -> web.Response:
    """Отвязывает токен Т-Инвестиций."""
    await users_api.delete_token(current_user(request).telegram_id)
    return web.json_response({"has_token": False})
