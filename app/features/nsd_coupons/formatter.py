"""Форматирование уведомлений о невыплаченных купонах для Telegram (HTML)."""

from __future__ import annotations

from html import escape

from .schemas import CouponMissAlert


def _format_amount(amount: float | None) -> str | None:
    """Форматирует сумму купона (``1234.5`` → ``1 234,5``) или ``None``."""
    if amount is None:
        return None
    text = f"{amount:,.2f}".replace(",", " ").replace(".", ",")
    return text.rstrip("0").rstrip(",") if "," in text else text


def format_coupon_miss(alert: CouponMissAlert) -> str:
    """Собирает HTML-сообщение о неполученном купоне.

    Args:
        alert: Данные о невыплаченном купоне.

    Returns:
        Готовый HTML-текст для отправки в Telegram.
    """
    name = escape(alert.bond_name or alert.issuer_name or alert.isin)
    lines = [
        "<b>⚠️ Купон не поступил в НРД</b>",
        "",
        f"Облигация: <b>{name}</b>",
        f"ISIN: <code>{escape(alert.isin)}</code>",
        f"Купон №{alert.coupon_number}",
        f"Плановая дата выплаты: {alert.coupon_date.strftime('%d.%m.%Y')}",
    ]
    amount = _format_amount(alert.amount)
    if amount is not None:
        lines.append(f"Ожидалось на 1 бумагу: {amount} ₽")
    lines.append("")
    lines.append(
        "По данным НРД выплата по этому купону не зафиксирована к плановой дате. "
        "Возможна задержка или технический дефолт эмитента."
    )
    return "\n".join(lines)
