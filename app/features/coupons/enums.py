"""Enums for coupons feature."""

from enum import Enum


class CouponCallbackData(Enum):
    """Кол-беки для инлайн-кнопок купонов."""

    COUPONS_TODAY = "coupons_today"
    COUPONS_WEEK = "coupons_week"
    COUPONS_MONTH = "coupons_month"


class CouponButtonTexts(Enum):
    """Тексты для инлайн-кнопок купонов."""

    TODAY = "Сегодня"
    WEEK = "Неделю"
    MONTH = "Месяц"
