"""Форматирование уведомлений об изменении рейтинга НРА для Telegram."""

from __future__ import annotations

from .schemas import RatingChange

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


def _format_single(change: RatingChange) -> str:
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
        bonds = ", ".join(change.matched_bond_names)
        lines.append(f"  В вашем портфеле: {bonds}")

    return "\n".join(lines)


def format_rating_alert(changes: list[RatingChange]) -> str:
    """Формирует HTML-сообщение об изменениях рейтинга по бумагам пользователя.

    Args:
        changes: Список изменений, затрагивающих портфель пользователя.

    Returns:
        Отформатированное HTML-сообщение.

    """
    blocks: list[str] = ["<b>📊 Обновление кредитного рейтинга по вашим облигациям</b>\n"]
    blocks.extend(_format_single(change) for change in changes)
    return "\n".join(blocks)
