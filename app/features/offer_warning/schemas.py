"""Схемы фичи offer_warning: callback-данные и payload события оферты."""

from __future__ import annotations

from datetime import date
from typing import Literal

from aiogram.filters.callback_data import CallbackData
from pydantic import BaseModel


class BondOffer(BaseModel):
    """Данные о приближающейся оферте облигации.

    Приходит в payload события от внешнего сервиса мониторинга оферт.
    """

    isin: str
    name: str

    issuevalue: int | None = None

    offerdate: date
    offerdatestart: date | None = None
    offerdateend: date | None = None

    facevalue: float
    faceunit: str

    price: float | None = None
    value: float | None = None

    agent: str | None = None
    offertype: str | None = None

    secid: str
    primary_boardid: str | None = None


class OfferAlertCallback(CallbackData, prefix="offer"):
    """Callback data для инлайн-кнопок уведомлений об офертах."""

    action: Literal["toggle", "setting", "set_first", "set_second", "set_time"]
