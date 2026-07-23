"""Форматирование уведомлений об офертах для отправки в Telegram."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from common.utils.bot_utils import pluralize_days

from .schemas import BondOffer

_MSK_TZ = ZoneInfo("Europe/Moscow")


def _fmt_date(d) -> str:
    return d.strftime("%d.%m.%Y") if d else "—"


def _format_single_offer(offer: BondOffer, days_until: int) -> str:
    moex_link = (
        f"https://www.moex.com/ru/issue.aspx"
        f"?board={offer.primary_boardid}&code={offer.secid}"
    )

    lines: list[str] = [
        f'• <a href="{moex_link}"><b>{offer.name}</b></a>',
        f"  Дата оферты: <b>{_fmt_date(offer.offerdate)}</b> "
        f"— осталось <b>{days_until} {pluralize_days(days_until)}</b>",
    ]

    if offer.offerdatestart or offer.offerdateend:
        window = f"{_fmt_date(offer.offerdatestart)} – {_fmt_date(offer.offerdateend)}"
        lines.append(f"  Приём заявок: {window}")

    currency = offer.faceunit.upper() if offer.faceunit else ""
    if offer.price is not None:
        lines.append(
            f"  Цена выкупа: <b>{offer.facevalue:,.0f} {currency}</b> "
            f"({offer.price:.2f}% от номинала)"
        )
    else:
        lines.append(f"  Цена выкупа: <b>{offer.facevalue:,.0f} {currency}</b>")

    if offer.agent:
        lines.append(f"  Агент: {offer.agent}")

    return "\n".join(lines)


def format_offer_alerts(offers: list[BondOffer]) -> str:
    """Формирует HTML-сообщение с перечнем приближающихся оферт.

    Args:
        offers: Список оферт из MOEX.

    Returns:
        Отформатированное HTML-сообщение.

    """
    today = datetime.now(_MSK_TZ).date()
    blocks: list[str] = ["<b>⚠️ Приближается оферта (PUT-опцион)</b>\n"]

    last_deadline: str | None = None
    for offer in offers:
        days_until = (offer.offerdate - today).days
        blocks.append(_format_single_offer(offer, days_until))
        if offer.offerdateend:
            last_deadline = _fmt_date(offer.offerdateend)

    if last_deadline:
        blocks.append(
            f"\nПодайте поручение брокеру <b>до {last_deadline}</b> — "
            "приём заявок закрывается раньше даты оферты."
        )
    else:
        blocks.append(
            "\nНе забудьте подать поручение брокеру заранее — "
            "обычно приём заявок закрывается за несколько дней до даты оферты."
        )

    return "\n".join(blocks)
