"""Форматирование уведомлений о раскрытиях эмитентов для Telegram."""

from __future__ import annotations

from html import escape

from common.scope import AlertScope, with_market_hint

from .enums import (
    CIRCUMSTANCE_TITLES,
    DEFAULT_KIND_TITLES,
    OBLIGATION_TITLES,
    RISK_ICONS,
    RISK_TITLES,
)
from .schemas import DisclosureAlert

# Неразрывный пробел как разделитель тысяч — число не переносится в Telegram.
_NBSP = " "


def _format_money(value: float) -> str:
    """Форматирует сумму: ``1 647 440,01``."""
    return f"{value:,.2f}".replace(",", _NBSP).replace(".", ",")


def _event_title(alert: DisclosureAlert) -> str | None:
    """Человеческое название события — по типу раскрытия.

    `signal_type` несёт разное для разных типов: у обстоятельств это вид
    обстоятельства, у неисполнений — вид обязательства.
    """
    if alert.source_type == "default":
        obligation = alert.obligation_type or alert.signal_type
        title = OBLIGATION_TITLES.get(obligation or "", "Неисполнение обязательства")
        kind = DEFAULT_KIND_TITLES.get(alert.default_kind or "")
        return f"{title} — {kind}" if kind else title

    circumstance = alert.circumstance_type or alert.signal_type
    return CIRCUMSTANCE_TITLES.get(circumstance or "")


def _format_single(alert: DisclosureAlert) -> str:
    """Форматирует блок одного раскрытия."""
    icon = RISK_ICONS.get(alert.risk_level, "•")
    risk = RISK_TITLES.get(alert.risk_level, alert.risk_level)

    lines = [f"{icon} <b>{escape(alert.issuer_name)}</b> — {risk}"]

    title = _event_title(alert)
    if title:
        lines.append(f"  {escape(title)}")

    if alert.unfulfilled_amount:
        lines.append(f"  Не исполнено: {_format_money(alert.unfulfilled_amount)} ₽")

    if alert.event_date:
        lines.append(f"  Дата события: {escape(alert.event_date)}")

    lines.append(f"\n{escape(alert.summary)}")

    if alert.matched_bonds:
        bonds = "\n".join(
            f"{escape(bond.name)} <code>{escape(bond.isin)}</code>"
            for bond in alert.matched_bonds
        )
        lines.append(f"\nЗатронутые выпуски:\n{bonds}")

    return "\n".join(lines)


def format_disclosure_alert(
    alerts: list[DisclosureAlert], scope: AlertScope = AlertScope.PORTFOLIO
) -> str:
    """Формирует HTML-сообщение о раскрытиях.

    Args:
        alerts: Раскрытия. Для аудитории ``PORTFOLIO`` они уже отфильтрованы по
            бумагам пользователя, для ``MARKET`` — нет.
        scope: Аудитория события — влияет только на шапку и приписку.

    Returns:
        Отформатированное HTML-сообщение.

    """
    header = (
        "<b>📄 Раскрытие эмитента</b>"
        if scope.is_market
        else "<b>📄 Раскрытие по вашим облигациям</b>"
    )
    blocks = [header]
    blocks.extend(_format_single(alert) for alert in alerts)
    return with_market_hint("\n\n".join(blocks), scope)
