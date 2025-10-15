"""Модуль обработчиков бота."""

from .coupon_handlers import CouponHandler
from .registration import register_handlers

__all__ = ["CouponHandler", "register_handlers"]
