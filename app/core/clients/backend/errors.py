"""Ошибки клиента бэкенда."""


class BackendError(Exception):
    """Базовая ошибка обращения к бэкенду."""


class BackendAuthError(BackendError):
    """Не удалось получить OIDC id-token для вызова приватного Cloud Run сервиса."""


class BackendNotConfigured(BackendError):
    """Не задан базовый URL бэкенда (`BACKEND_URL`)."""


class UserNotFound(BackendError):
    """Бэкенд не знает такого пользователя (HTTP 404, code=not_found)."""
