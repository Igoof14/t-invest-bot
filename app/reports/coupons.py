import datetime
from datetime import time, timedelta

from aiogram import Bot
from core.enums import ReportType
from invest import get_coupon_payment


async def send_report(bot: Bot, report_type: ReportType, users: set[int]):
    """Рассылка отчёта."""
    if not users:
        return

    if report_type.value == "daily":
        start_datetime = datetime.combine(datetime.today().date(), time.min)
    elif report_type.value == "weekly":
        today = datetime.today()
        start_datetime = datetime.combine(
            today.date() - timedelta(days=today.weekday()),
            time.min,
        )

    text = get_coupon_payment(start_datetime=start_datetime)
    for uid in users:
        try:
            await bot.send_message(uid, text, parse_mode="HTML")
        except Exception as e:
            print(f"Ошибка при отправке {uid}: {e}")
