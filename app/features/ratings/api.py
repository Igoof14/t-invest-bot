"""HTTP endpoint приёма событий об изменении кредитных рейтингов."""

from __future__ import annotations

import logging

from aiohttp import web
from api.keys import BOT_KEY
from pydantic import BaseModel, Field, ValidationError

from .notifier import RatingAlertNotifier
from .schemas import RatingChange

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()


class RatingAlertEvent(BaseModel):
    """Событие «изменения рейтингов для пользователя»."""

    telegram_id: int
    alerts: list[RatingChange] = Field(min_length=1)


@routes.post("/events/rating-change")
async def handle_rating_change(request: web.Request) -> web.Response:
    """Принимает событие об изменениях рейтингов и уведомляет пользователя.

    Невалидный payload подтверждается (200), чтобы Cloud Tasks не
    ретраил заведомо неисправимую задачу. Ошибка отправки — 503 (ретрай).
    """
    try:
        event = RatingAlertEvent.model_validate(await request.json())
    except (ValidationError, ValueError) as e:
        logger.error("Невалидный payload rating-change: %s", e)
        return web.json_response({"status": "dropped", "reason": "invalid payload"})

    notifier = RatingAlertNotifier(request.app[BOT_KEY])
    sent = await notifier.send(event.telegram_id, event.alerts)

    if not sent:
        return web.json_response({"status": "error"}, status=503)
    return web.json_response({"status": "sent"})
