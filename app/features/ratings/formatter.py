"""Форматирование уведомлений об изменении рейтинга для Telegram (общее)."""

from __future__ import annotations

from common.scope import AlertScope, with_market_hint

# Иконка по каноничному рейтинговому действию.
_ACTION_ICONS = {
    "Понижен": "🔻",
    "Отозван": "⚠️",
    "Повышен": "🔼",
    "Присвоен": "🆕",
    "Подтверждён": "✅",
    "Изменён": "🔄",
    "Пересмотр": "🔄",
}


def _format_single(change) -> str:
    """Форматирует один блок изменения рейтинга."""
    event = change.event
    icon = _ACTION_ICONS.get(event.rating_action or "", "•")
    name = event.entity_name or "Эмитент"

    lines: list[str] = [f'{icon} <a href="{event.url}"><b>{name}</b></a>']

    rating_bits: list[str] = []
    if event.rating_action:
        rating_bits.append(f"<b>{event.rating_action}</b>")
    if event.rating_value:
        rating_bits.append(event.rating_value)
    if rating_bits:
        lines.append("  Рейтинг: " + " — ".join(rating_bits))

    if event.outlook:
        lines.append(f"  Прогноз: {event.outlook}")

    if change.matched_bond_names:
        bonds = ", ".join(
            f"{bond.name} <code>{bond.isin}</code>" for bond in change.matched_bond_names
        )
        lines.append(f"  В вашем портфеле:\n{bonds}")

    return "\n".join(lines)


def format_rating_alert(changes: list, scope: AlertScope = AlertScope.PORTFOLIO) -> str:
    """Формирует HTML-сообщение об изменениях рейтинга.

    Args:
        changes: Список изменений. Для аудитории ``PORTFOLIO`` они уже
            отфильтрованы по бумагам пользователя, для ``MARKET`` — нет.
        scope: Аудитория события — влияет только на шапку и приписку.

    Returns:
        Отформатированное HTML-сообщение.

    """
    header = (
        "<b>📊 Обновление кредитных рейтингов</b>"
        if scope.is_market
        else "<b>📊 Обновление кредитного рейтинга по вашим облигациям</b>"
    )
    blocks: list[str] = [header]
    blocks.extend(_format_single(change) for change in changes)
    return with_market_hint("\n\n".join(blocks), scope)
