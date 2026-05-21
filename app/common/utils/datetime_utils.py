"""Утилиты для работы с датами и временем."""

from datetime import datetime, time, timedelta


class DateTimeHelper:
    """Хелпер для работы с датами."""

    @staticmethod
    def get_today_start() -> datetime:
        """Возвращает начало текущего дня."""
        return datetime.combine(datetime.today().date(), time.min)

    @staticmethod
    def get_week_start() -> datetime:
        """Возвращает начало текущей недели (понедельник)."""
        today = datetime.today()
        return datetime.combine(
            today.date() - timedelta(days=today.weekday()),
            time.min,
        )

    @staticmethod
    def get_month_start() -> datetime:
        """Возвращает начало текущего месяца."""
        today = datetime.today()
        return datetime.combine(
            today.date() - timedelta(days=today.day - 1),
            time.min,
        )
