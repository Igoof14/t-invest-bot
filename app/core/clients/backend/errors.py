"""Ошибки клиента бэкенда."""


class BackendError(Exception):
    """Базовая ошибка обращения к бэкенду."""


class BackendAuthError(BackendError):
    """Не удалось получить OIDC id-token для вызова приватного Cloud Run сервиса."""


class BackendNotConfigured(BackendError):
    """Не задан базовый URL бэкенда (`BACKEND_URL`)."""


class UserNotFound(BackendError):
    """Бэкенд не знает такого пользователя (HTTP 404, code=not_found)."""


class InvalidToken(BackendError):
    """T-Invest отверг токен (HTTP 400, code=invalid_token).

    Виноват именно токен: бэкенд спросил у брокера и получил отказ. Пользователю
    имеет смысл прислать токен заново.
    """


class UpstreamUnavailable(BackendError):
    """Бэкенд не смог достучаться до T-Invest (HTTP 503, code=upstream_unavailable).

    Это не приговор токену: проверка не состоялась, и повторить её стоит позже.
    """
