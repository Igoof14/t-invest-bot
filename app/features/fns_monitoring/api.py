"""HTTP endpoint приёма событий о блокировках счетов ФНС."""

from __future__ import annotations

import logging

from aiohttp import web
from api.keys import BOT_KEY
from api.responses import delivery_response
from pydantic import BaseModel, Field, ValidationError

from .events import BlockingOrder, MatchedBond, UserBlockAlert
from .notifier import FnsBlockNotifier

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()


class MatchedBondPayload(BaseModel):
    """Облигация пользователя, затронутая блокировкой."""

    name: str
    ticker: str | None = None


class UserBlockAlertPayload(BaseModel):
    """Блокировки одного эмитента, затрагивающие портфель пользователя."""

    inn: str
    entity_name: str | None = None
    orders: list[BlockingOrder]
    matched_bonds: list[MatchedBondPayload]

    def to_domain(self) -> UserBlockAlert:
        """Преобразует payload в доменный объект UserBlockAlert."""
        return UserBlockAlert(
            inn=self.inn,
            entity_name=self.entity_name,
            orders=self.orders,
            matched_bonds=[MatchedBond(name=b.name, ticker=b.ticker) for b in self.matched_bonds],
        )


class FnsBlockEvent(BaseModel):
    """Событие «блокировки ФНС для пользователя»."""

    telegram_id: int
    alerts: list[UserBlockAlertPayload] = Field(min_length=1)


@routes.post("/events/fns-block")
async def handle_fns_block(request: web.Request) -> web.Response:
    """Принимает событие о блокировках ФНС и уведомляет пользователя.

    Невалидный payload и постоянные ошибки доставки подтверждаются (200),
    чтобы Cloud Tasks не ретраил заведомо неисправимую задачу. Ретрай имеет
    смысл только при временной ошибке — тогда 503.
    """
    try:
        event = FnsBlockEvent.model_validate(await request.json())
    except (ValidationError, ValueError) as e:
        logger.error("Невалидный payload fns-block: %s", e)
        return web.json_response({"status": "dropped", "reason": "invalid payload"})

    notifier = FnsBlockNotifier(request.app[BOT_KEY])
    alerts = [a.to_domain() for a in event.alerts]
    result = await notifier.send(event.telegram_id, alerts)
    return delivery_response(result)
