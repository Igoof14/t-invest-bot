"""Форматирование уведомлений о блокировках счетов ФНС для Telegram."""

from __future__ import annotations

from html import escape

from .events import BlockingOrder, UserBlockAlert, UserScanReport

# Расшифровка кода основания приостановления операций по счетам.
_REASON_BY_CODE = {
    "1": "Решение о взыскании задолженности",
    "2": "Непредставление налоговой декларации",
    "3": "Обеспечение исполнения решения по проверке",
    "4": "Непередача квитанции о приёме требования",
    "5": "Необеспечение электронного документооборота",
    "6": "Непредставление расчёта НДФЛ/взносов",
}


def _format_order(order: BlockingOrder) -> str:
    """Форматирует одну строку решения о блокировке."""
    bits: list[str] = []
    if order.nomer:
        nomer = escape(order.nomer)
        date = f" от {escape(order.decision_date)}" if order.decision_date else ""
        bits.append(f"Решение №{nomer}{date}")
    if order.bik:
        bits.append(f"БИК {escape(order.bik)}")
    if order.kod_osnov:
        reason = _REASON_BY_CODE.get(order.kod_osnov, f"код {escape(order.kod_osnov)}")
        bits.append(reason)
    if order.saldo:
        bits.append(f"сальдо {escape(order.saldo)} ₽")
    return "  • " + " | ".join(bits)


def _format_single(alert: UserBlockAlert) -> str:
    """Форматирует блок одного эмитента."""
    name = escape(alert.entity_name or f"ИНН {alert.inn}")
    lines: list[str] = [f"🚫 <b>{name}</b>"]
    lines.extend(_format_order(order) for order in alert.orders)
    if alert.matched_bond_names:
        bonds = escape(", ".join(alert.matched_bond_names))
        lines.append(f"  В вашем портфеле: {bonds}")
    return "\n".join(lines)


def format_fns_alert(alerts: list[UserBlockAlert]) -> str:
    """Формирует HTML-сообщение о блокировках счетов по бумагам пользователя.

    Args:
        alerts: Блокировки эмитентов, затрагивающие портфель пользователя.

    Returns:
        Отформатированное HTML-сообщение.

    """
    header = (
        "<b>🚫 ФНС: приостановление операций по счетам "
        "по вашим облигациям</b>\n"
    )
    blocks: list[str] = [header]
    blocks.extend(_format_single(alert) for alert in alerts)
    return "\n".join(blocks)


def format_scan_report(report: UserScanReport) -> str:
    """Формирует ответ на разовую проверку эмитентов пользователя.

    Args:
        report: Результат проверки.

    Returns:
        HTML-сообщение с итогом проверки.

    """
    if report.no_token:
        return (
            "⚠️ Не найден токен T-Invest. Добавьте его в настройках, "
            "чтобы проверить эмитентов вашего портфеля."
        )
    if report.no_bonds:
        return "В вашем портфеле нет облигаций для проверки."
    if report.checked == 0:
        return "Не удалось сопоставить ваши облигации с эмитентами реестра."

    if not report.blocked:
        return (
            f"✅ Проверено эмитентов: {report.checked}.\n"
            "Действующих блокировок счетов не найдено."
        )

    lines: list[str] = [
        f"<b>🚫 Найдены блокировки счетов ({len(report.blocked)}):</b>\n"
    ]
    lines.extend(_format_single(alert) for alert in report.blocked)
    lines.append(f"\nПроверено эмитентов: {report.checked}.")
    return "\n".join(lines)
