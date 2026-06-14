"""Пул прокси для запросов к ФНС: парсинг и нормализация в URL."""

from __future__ import annotations

import logging
import re

from core.config import config

logger = logging.getLogger(__name__)

# Разделители элементов списка прокси в .env.
_SPLIT_RE = re.compile(r"[,\n\s]+")
# Схемы, которые принимаем как готовый URL.
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")


def normalize_proxy(raw: str) -> str:
    """Нормализует строку прокси в URL вида ``http://[user:pass@]host:port``.

    Поддерживает:
      * готовый URL со схемой (``http://``/``socks5://``) — возвращается как есть;
      * формат провайдера ``ip:port:user:pass`` → ``http://user:pass@ip:port``;
      * ``host:port`` → ``http://host:port``.

    Args:
        raw: Сырая строка прокси.

    Returns:
        Нормализованный URL прокси.

    Raises:
        ValueError: Если строку нельзя распознать.

    """
    value = raw.strip()
    if not value:
        raise ValueError("пустая строка прокси")

    if _SCHEME_RE.match(value):
        return value

    parts = value.split(":")
    if len(parts) == 2:
        host, port = parts
        return f"http://{host}:{port}"
    if len(parts) == 4:
        host, port, user, password = parts
        return f"http://{user}:{password}@{host}:{port}"

    raise ValueError(f"не распознан формат прокси: {raw!r}")


def load_proxies() -> list[str | None]:
    """Загружает пул прокси для ФНС из конфигурации.

    Берёт ``config.fns_proxies`` (список), иначе одиночный ``config.fns_proxy``.
    Если ничего не задано — возвращает ``[None]`` (прямое соединение).

    Returns:
        Список URL прокси; ``[None]`` означает один «прямой» воркер.

    """
    raw = config.fns_proxies or config.fns_proxy
    if not raw:
        return [None]

    proxies: list[str | None] = []
    for token in _SPLIT_RE.split(raw):
        if not token:
            continue
        try:
            proxies.append(normalize_proxy(token))
        except ValueError as e:
            logger.warning("Пропущен некорректный прокси: %s", e)

    return proxies or [None]
