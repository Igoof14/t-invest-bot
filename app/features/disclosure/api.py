"""HTTP endpoint приёма событий о раскрытиях эмитентов."""

from __future__ import annotations

import logging

from aiohttp import web
from api.keys import BOT_KEY
from api.responses import delivery_response
from common.scope import AlertScope
from pydantic import BaseModel, Field, ValidationError

from .notifier import DisclosureAlertNotifier
from .schemas import DisclosureAlert

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()


class DisclosureAlertEvent(BaseModel):
    """Событие «раскрытия эмитента для пользователя».

    Получателя и его бумаги резолвит продюсер (`disclosure-parsing-worker`) —
    сюда приезжает уже персональный конверт.
    """

    telegram_id: int
    alerts: list[DisclosureAlert] = Field(min_length=1)
    scope: AlertScope = AlertScope.PORTFOLIO


@routes.post("/events/disclosure")
async def handle_disclosure(request: web.Request) -> web.Response:
    """Принимает раскрытия эмитента и уведомляет пользователя.

    Невалидный payload и постоянные ошибки доставки подтверждаются (200),
    чтобы Cloud Tasks не ретраил заведомо неисправимую задачу. Ретрай имеет
    смысл только при временной ошибке — тогда 503.
    """
    try:
        event = DisclosureAlertEvent.model_validate(await request.json())
    except (ValidationError, ValueError) as e:
        logger.error("Невалидный payload disclosure: %s", e)
        return web.json_response({"status": "dropped", "reason": "invalid payload"})

    notifier = DisclosureAlertNotifier(request.app[BOT_KEY])
    result = await notifier.send(event.telegram_id, event.alerts, scope=event.scope)
    return delivery_response(result)
