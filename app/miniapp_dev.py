"""Локальный сервер BFF мини-аппа — без webhook, Telegram и БД.

Полный бот поднимать ради вёрстки незачем: он работает по webhook и требует
туннеля с публичным HTTPS. Здесь стартуют только роуты ``/miniapp/api``, и
фронтенду этого достаточно — за данными они всё равно ходят в бэкенд.

Запуск:

    uv run python app/miniapp_dev.py

Нужны две переменные в ``.env``:

    BACKEND_URL=http://127.0.0.1:8000     # loopback — запросы идут без OIDC
    MINIAPP_DEV_TELEGRAM_ID=<ваш id>      # разрешает запросы без подписи Telegram

Прод этот модуль не использует: там роуты подключены к общему приложению в
``api/server.py``.
"""

from __future__ import annotations

import logging

from aiohttp import web
from core.config import config
from features.miniapp import api as miniapp_api
from features.miniapp import auth_middleware, create_cors_middleware, no_store_middleware

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

# Порт тот же, что у боевого сервиса: dev-сервер Vite проксирует на него.
DEV_PORT = 8080

# Источник dev-сервера Vite. Берётся из конфига, если задан, — на случай другого
# порта; иначе значение по умолчанию, чтобы CORS работал без лишних настроек.
DEFAULT_ORIGIN = "http://localhost:5173"


def create_app() -> web.Application:
    """Приложение только с роутами мини-аппа."""
    origin = config.miniapp_origin or DEFAULT_ORIGIN
    app = web.Application(
        middlewares=[create_cors_middleware(origin), no_store_middleware, auth_middleware]
    )
    app.add_routes(miniapp_api.routes)
    return app


def main() -> None:
    """Проверяет конфигурацию и запускает сервер."""
    if config.miniapp_dev_telegram_id is None:
        logger.warning(
            "MINIAPP_DEV_TELEGRAM_ID не задан: запросы без подписи Telegram будут "
            "отклонены с 401. Открыть мини-апп в обычном браузере не получится."
        )
    if not config.backend_url:
        logger.error("BACKEND_URL не задан — все запросы вернут 502")

    logger.info("BFF мини-аппа: http://127.0.0.1:%s/miniapp/api", DEV_PORT)
    web.run_app(create_app(), host="127.0.0.1", port=DEV_PORT)


if __name__ == "__main__":
    main()
