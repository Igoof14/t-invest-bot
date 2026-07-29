"""Форматирование уведомлений о блокировках счетов ФНС для Telegram."""

from __future__ import annotations

from html import escape

from common.scope import AlertScope, with_market_hint

from .events import BlockingOrder, MatchedBond, UserBlockAlert, UserScanReport


def _parse_saldo(raw: str | None) -> float | None:
    """Преобразует строку сальдо ФНС в число (или ``None``)."""
    if not raw:
        return None
    cleaned = raw.replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _max_saldo(orders: list[BlockingOrder]) -> float | None:
    """Возвращает максимальное (по модулю) отрицательное сальдо ЕНС по решениям."""
    values = [v for v in (_parse_saldo(o.saldo) for o in orders) if v is not None]
    return max(values) if values else None


# Неразрывный пробел как разделитель тысяч — число не переносится в Telegram.
_NBSP = "\u00a0"


def _format_money(value: float) -> str:
    """Форматирует сумму с разделителем тысяч и двумя знаками: ``1 647 440,01``."""
    return f"{value:,.2f}".replace(",", _NBSP).replace(".", ",")


def _format_bond(bond: MatchedBond) -> str:
    """Форматирует облигацию: тикер в ``<code>`` (копируется по тапу) + имя."""
    name = escape(bond.name)
    if bond.ticker and bond.ticker != bond.name:
        return f"<code>{escape(bond.ticker)}</code> {name}"
    if bond.ticker:
        return f"<code>{escape(bond.ticker)}</code>"
    return name


def _format_single(alert: UserBlockAlert, scope: AlertScope = AlertScope.PORTFOLIO) -> str:
    """Форматирует агрегированный блок одного эмитента.

    Для рыночной аудитории ``matched_bonds`` — это бумаги эмитента, а не
    портфель получателя, поэтому и подпись к списку другая.
    """
    name = escape(alert.entity_name or "Эмитент")
    lines: list[str] = [
        f"<b>{name}</b>",
        f"ИНН: <code>{escape(alert.inn)}</code>",
        f"Заблокировано счетов: {len(alert.orders)}",
    ]
    saldo = _max_saldo(alert.orders)
    if saldo is not None:
        lines.append(f"Отрицательное сальдо: {_format_money(saldo)} ₽")
    if alert.matched_bonds:
        bonds = "\n".join(_format_bond(b) for b in alert.matched_bonds)
        label = "Облигации эмитента" if scope.is_market else "В вашем портфеле"
        lines.append(f"\n{label}:\n{bonds}")
    return "\n".join(lines)


def format_fns_alert(alerts: list[UserBlockAlert], scope: AlertScope = AlertScope.PORTFOLIO) -> str:
    """Формирует HTML-сообщение о блокировках счетов эмитентов.

    Args:
        alerts: Блокировки эмитентов. Для аудитории ``PORTFOLIO`` они уже
            отфильтрованы по бумагам пользователя, для ``MARKET`` — нет.
        scope: Аудитория события — влияет только на формулировки.

    Returns:
        Отформатированное HTML-сообщение.

    """
    header = (
        "<b>🚫 ФНС: заблокированы счета эмитента облигаций</b>"
        if scope.is_market
        else "<b>🚫 ФНС: заблокированы счета ваших эмитентов</b>"
    )
    blocks: list[str] = [header]
    blocks.extend(_format_single(alert, scope) for alert in alerts)
    return with_market_hint("\n\n".join(blocks), scope)


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
            f"✅ Проверено эмитентов: {report.checked}.\nДействующих блокировок счетов не найдено."
        )

    lines: list[str] = [f"<b>🚫 Найдены блокировки счетов ({len(report.blocked)}):</b>"]
    lines.extend(_format_single(alert) for alert in report.blocked)
    lines.append(f"Проверено эмитентов: {report.checked}.")
    return "\n\n".join(lines)
