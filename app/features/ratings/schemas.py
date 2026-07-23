"""Схемы фичи ratings: callback-данные и payload события изменения рейтинга."""

from __future__ import annotations

from typing import Literal

from aiogram.filters.callback_data import CallbackData
from pydantic import BaseModel, Field


class RatingEvent(BaseModel):
    """Одно рейтинговое действие агентства по эмитенту.

    Приходит в payload события от внешнего сервиса мониторинга рейтингов.
    """

    entity_name: str | None = None
    url: str
    rating_action: str | None = None
    rating_value: str | None = None
    outlook: str | None = None


class RatingMatchedBond(BaseModel):
    """Облигация пользователя, затронутая изменением рейтинга."""

    isin: str
    name: str


class RatingChange(BaseModel):
    """Изменение рейтинга, затрагивающее портфель пользователя."""

    event: RatingEvent
    matched_bond_names: list[RatingMatchedBond] = Field(default_factory=list)


class RatingAlertCallback(CallbackData, prefix="rating"):
    """Callback data для тумблеров подписки на рейтинговые агентства."""

    action: Literal["toggle"]
    # Значение RatingAgency (например, "nra").
    agency: str
