"""Единый маппинг итога доставки в HTTP-ответ для Cloud Tasks."""

from __future__ import annotations

from aiohttp import web
from common.delivery import DeliveryResult

__all__ = ["delivery_response"]


def delivery_response(result: DeliveryResult) -> web.Response:
    """Превращает итог доставки в ответ, понятный Cloud Tasks.

    Cloud Tasks ретраит любой не-2xx, поэтому постоянные ошибки
    (заблокировавший бота пользователь, некорректный запрос) подтверждаются
    статусом 200 — иначе задача ретраится бесконечно.
    """
    if result.is_sent:
        return web.json_response({"status": "sent"})
    if result.should_retry:
        return web.json_response({"status": "error", "reason": result.reason}, status=503)
    return web.json_response({"status": "dropped", "reason": result.reason})
