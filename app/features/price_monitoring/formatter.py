"""Форматирование текста уведомлений об аномалиях цен.

Чистые функции без зависимостей на бот, БД или сеть — легко тестируются.
"""

from collections.abc import Sequence

from .schemas import PriceAnomaly


def format_single_alert(anomaly: PriceAnomaly) -> str:
    """Формирует HTML-сообщение для одной аномалии."""
    if anomaly.is_critical:
        if anomaly.is_drop:
            header = "<b>🚨КРИТИЧЕСКОЕ падение цены!</b>"
        else:
            header = "<b>🚨КРИТИЧЕСКИЙ рост цены!</b>"
    else:
        header = "<b>Внимание: изменение цены облигации</b>"

    direction_text = "упала" if anomaly.is_drop else "выросла"

    lines = [
        header,
        "",
        f"<code>{anomaly.isin}</code>",
        f"{anomaly.name}",
        "",
        f"Цена {direction_text} на {abs(anomaly.change_pct):.1f}%",
        f"   Было: {anomaly.prev_close_pct:.2f}%  →  Стало: {anomaly.price_pct:.2f}%",
    ]

    if anomaly.is_critical:
        lines.append("")
        lines.append("⚡ <i>Рекомендуем проверить новости эмитента</i>")

    return "\n".join(lines)


def format_aggregated_alert(
    anomalies: Sequence[PriceAnomaly],
    *,
    max_per_severity: int,
) -> tuple[str, list[PriceAnomaly]]:
    """Формирует сводное сообщение по нескольким аномалиям.

    Args:
        anomalies: Список аномалий (предполагается, что уже отфильтрован
            антиспам-политикой).
        max_per_severity: Максимум аномалий, показываемых по каждому уровню
            критичности (CRITICAL / WARNING).

    Returns:
        Кортеж ``(сообщение, показанные_аномалии)``. ``показанные_аномалии`` —
        подмножество ``anomalies``, реально упомянутое в тексте. Этот список
        нужен для записи факта отправки.

    """
    critical = [a for a in anomalies if a.is_critical]
    warnings = [a for a in anomalies if not a.is_critical]

    shown_critical = critical[:max_per_severity]
    shown_warnings = warnings[:max_per_severity]
    shown = shown_critical + shown_warnings

    lines = ["<b>Множественные изменения цен облигаций</b>\n"]

    if critical:
        lines.append(f"<b>Критических: {len(critical)}</b>")
        lines.extend(_format_summary_rows(shown_critical))

    if warnings:
        lines.append(f"\n<b>Предупреждений: {len(warnings)}</b>")
        lines.extend(_format_summary_rows(shown_warnings))

    not_shown = len(anomalies) - len(shown)
    if not_shown > 0:
        lines.append(f"\n... и ещё {not_shown} изменений")

    lines.append("\n<i>Рекомендуем проверить портфель</i>")

    return "\n".join(lines), shown


def _format_summary_rows(anomalies: Sequence[PriceAnomaly]) -> list[str]:
    """Форматирует строки сводки для группы аномалий одного уровня."""
    return [
        f"  {'[-]' if a.is_drop else '[+]'} <code>{a.isin}</code>: {a.change_pct:+.1f}%"
        for a in anomalies
    ]
