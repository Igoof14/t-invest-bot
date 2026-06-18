"""Форматирование уведомлений о невыплаченных купонах для Telegram (HTML)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from html import escape
from zoneinfo import ZoneInfo

from .schemas import CouponMissAlert, CouponScanReport, ScannedCoupon

_MSK = ZoneInfo("Europe/Moscow")


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


def _day_label(day: date, today: date) -> str:
    """Возвращает относительную подпись дня («Сегодня»/«Вчера»/дата)."""
    if day == today:
        return "Сегодня"
    if day == today - timedelta(days=1):
        return "Вчера"
    return day.strftime("%d.%m")


def format_scan_report(report: CouponScanReport) -> str:
    """Собирает HTML-сводку разовой проверки купонов за вчера и сегодня.

    Args:
        report: Результат проверки.

    Returns:
        HTML-сообщение со сводкой по дням и списком непоступивших купонов.

    """
    if report.no_token:
        return (
            "⚠️ Не найден токен T-Invest. Добавьте его в настройках, "
            "чтобы проверить ваши купоны."
        )
    if not report.coupons:
        return "За вчера и сегодня выплат по вашим облигациям не запланировано."

    today = datetime.now(_MSK).date()
    by_date: dict[date, list[ScannedCoupon]] = defaultdict(list)
    for coupon in report.coupons:
        by_date[coupon.coupon_date].append(coupon)

    lines = ["<b>🔍 Проверка купонов</b>", ""]
    unpaid: list[ScannedCoupon] = []
    for day in sorted(by_date):
        items = by_date[day]
        paid = sum(1 for c in items if c.paid)
        lines.append(
            f"{_day_label(day, today)} ({day.strftime('%d.%m')}): "
            f"выплачено {paid} из {len(items)}"
        )
        unpaid.extend(c for c in items if not c.paid)

    lines.append("")
    if unpaid:
        lines.append("❗ Не поступили:")
        for coupon in sorted(unpaid, key=lambda c: (c.coupon_date, c.bond_name or c.isin)):
            name = escape(coupon.bond_name or coupon.isin)
            lines.append(
                f"• {name} (<code>{escape(coupon.isin)}</code>) — "
                f"{coupon.coupon_date.strftime('%d.%m')}"
            )
    else:
        lines.append("✅ Все купоны за период выплачены.")
    return "\n".join(lines)
