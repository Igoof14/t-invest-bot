"""HTTP endpoint приёма событий об изменении кредитных рейтингов."""

from __future__ import annotations

import logging

from aiohttp import web
from api.keys import BOT_KEY
from api.responses import delivery_response
from common.scope import AlertScope
from pydantic import BaseModel, Field, ValidationError

from .notifier import RatingAlertNotifier
from .schemas import RatingChange

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()


class RatingAlertEvent(BaseModel):
    """Событие «изменения рейтингов для пользователя»."""

    telegram_id: int
    alerts: list[RatingChange] = Field(min_length=1)
    # Продюсер, ещё не задеплоенный с поддержкой аудиторий, поля не пришлёт —
    # для него поведение остаётся прежним, «по портфелю».
    scope: AlertScope = AlertScope.PORTFOLIO


@routes.post("/events/rating-change")
async def handle_rating_change(request: web.Request) -> web.Response:
    """Принимает событие об изменениях рейтингов и уведомляет пользователя.

    Невалидный payload и постоянные ошибки доставки подтверждаются (200),
    чтобы Cloud Tasks не ретраил заведомо неисправимую задачу. Ретрай имеет
    смысл только при временной ошибке — тогда 503.
    """
    try:
        event = RatingAlertEvent.model_validate(await request.json())
    except (ValidationError, ValueError) as e:
        logger.error("Невалидный payload rating-change: %s", e)
        return web.json_response({"status": "dropped", "reason": "invalid payload"})

    notifier = RatingAlertNotifier(request.app[BOT_KEY])
    result = await notifier.send(event.telegram_id, event.alerts, scope=event.scope)
    return delivery_response(result)
