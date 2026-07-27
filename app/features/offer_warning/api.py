"""HTTP endpoint приёма событий о приближающихся офертах."""

from __future__ import annotations

import logging

from aiohttp import web
from api.keys import BOT_KEY
from api.responses import delivery_response
from pydantic import BaseModel, Field, ValidationError

from .notifier import OfferAlertNotifier
from .schemas import BondOffer

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()


class OfferWarningEvent(BaseModel):
    """Событие «приближающиеся оферты для пользователя»."""

    telegram_id: int
    offers: list[BondOffer] = Field(min_length=1)


@routes.post("/events/offer-warning")
async def handle_offer_warning(request: web.Request) -> web.Response:
    """Принимает событие об офертах и уведомляет пользователя.

    Невалидный payload и постоянные ошибки доставки подтверждаются (200),
    чтобы Cloud Tasks не ретраил заведомо неисправимую задачу. Ретрай имеет
    смысл только при временной ошибке — тогда 503.
    """
    try:
        event = OfferWarningEvent.model_validate(await request.json())
    except (ValidationError, ValueError) as e:
        logger.error("Невалидный payload offer-warning: %s", e)
        return web.json_response({"status": "dropped", "reason": "invalid payload"})

    notifier = OfferAlertNotifier(request.app[BOT_KEY])
    result = await notifier.send(event.telegram_id, event.offers)
    return delivery_response(result)
