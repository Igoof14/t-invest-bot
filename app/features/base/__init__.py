"""Базовые команды бота: /start, /cancel, главное меню, портфель."""

from .handlers import fallback_router, router

__all__ = ["fallback_router", "router"]
