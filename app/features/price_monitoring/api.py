"""HTTP endpoint приёма событий ценовых аномалий от внешнего монитора."""

from __future__ import annotations

import logging

from aiohttp import web
from api.keys import BOT_KEY
from pydantic import BaseModel, Field, ValidationError

from .config import DEFAULT_POLICY
from .notifier import PriceAlertNotifier
from .schemas import AlertType, PriceAnomaly

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()


class PriceAnomalyPayload(BaseModel):
    """Одна аномалия цены в payload события."""

    figi: str
    ticker: str
    name: str
    old_price: float
    new_price: float
    change_percent: float
    alert_type: AlertType
    account_name: str

    def to_domain(self) -> PriceAnomaly:
        """Преобразует payload в доменный объект PriceAnomaly."""
        return PriceAnomaly(
            figi=self.figi,
            ticker=self.ticker,
            name=self.name,
            old_price=self.old_price,
            new_price=self.new_price,
            change_percent=self.change_percent,
            alert_type=self.alert_type,
            account_name=self.account_name,
        )


class PriceAlertEvent(BaseModel):
    """Событие «аномалии цен для пользователя» от сервиса мониторинга."""

    telegram_id: int
    anomalies: list[PriceAnomalyPayload] = Field(min_length=1)


@routes.post("/events/price-alert")
async def handle_price_alert(request: web.Request) -> web.Response:
    """Принимает событие ценовых аномалий и уведомляет пользователя.

    Невалидный payload подтверждается (200), чтобы Cloud Tasks не
    ретраил заведомо неисправимую задачу. Ошибка отправки — 503 (ретрай).
    """
    try:
        event = PriceAlertEvent.model_validate(await request.json())
    except (ValidationError, ValueError) as e:
        logger.error("Невалидный payload price-alert: %s", e)
        return web.json_response({"status": "dropped", "reason": "invalid payload"})

    notifier = PriceAlertNotifier(request.app[BOT_KEY])
    anomalies = [a.to_domain() for a in event.anomalies]

    if len(anomalies) >= DEFAULT_POLICY.aggregate_threshold:
        sent = await notifier.send_aggregated(
            event.telegram_id,
            anomalies,
            max_per_severity=DEFAULT_POLICY.max_aggregated_per_severity,
        )
    else:
        results = [
            await notifier.send_single(event.telegram_id, anomaly)
            for anomaly in anomalies
        ]
        sent = all(results)

    if not sent:
        return web.json_response({"status": "error"}, status=503)
    return web.json_response({"status": "sent"})
