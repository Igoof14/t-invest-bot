"""Онбординг-воронка: прогрев нового пользователя до подключения токена."""

from .handlers import router, start_onboarding

__all__ = ["router", "start_onboarding"]
