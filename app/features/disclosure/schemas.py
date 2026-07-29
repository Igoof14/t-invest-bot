"""Схемы фичи disclosure: payload события и callback-данные настроек."""

from __future__ import annotations

from typing import Literal

from aiogram.filters.callback_data import CallbackData
from pydantic import BaseModel, Field

# Порядок важен: он же задаёт порядок кнопок выбора порога.
RISK_LEVELS: tuple[str, ...] = ("low", "medium", "high", "critical")

RiskLevel = Literal["low", "medium", "high", "critical"]


class DisclosureBond(BaseModel):
    """Выпуск, которого касается раскрытие."""

    isin: str
    name: str


class DisclosureAlert(BaseModel):
    """Одно раскрытие эмитента, разобранное `disclosure-parsing-worker`.

    Поля после `event_date` — специфичные для типа раскрытия, приходят не всегда:
    `circumstance_type` у сообщений ПВО об обстоятельствах, остальные три — у
    сообщений о неисполнении обязательств.
    """

    alert_key: str
    source_type: str
    risk_level: RiskLevel
    issuer_name: str
    issuer_inn: str | None = None
    summary: str
    signal_type: str | None = None
    event_date: str | None = None
    matched_bonds: list[DisclosureBond] = Field(default_factory=list)

    circumstance_type: str | None = None
    obligation_type: str | None = None
    default_kind: str | None = None
    unfulfilled_amount: float | None = None
    currency: str | None = None


class DisclosureAlertCallback(CallbackData, prefix="disclosure"):
    """Callback data тумблера подписки и выбора минимального уровня риска."""

    action: Literal["toggle", "level"]
    # Заполняется только для action="level".
    level: str = ""
