# tinek-invest

Telegram-бот управления портфелем облигаций T-Invest. Работает через **webhook**
и разворачивается как Google Cloud Run service.

## Локальный запуск через туннель

Бот работает по webhook, поэтому Telegram должен достучаться до сервиса по
публичному HTTPS — `localhost` не подойдёт, нужен туннель.

1. Поднять Postgres (в `.env` нужен `POSTGRES_PASSWORD`, совпадающий с
   `DATABASE_URL`):
   ```bash
   docker compose -f docker-compose.db.yml up -d
   ```
2. Пробросить порт `8080` наружу и скопировать выданный **https**-URL:
   ```bash
   ngrok http 8080
   # или: cloudflared tunnel --url http://localhost:8080
   ```
3. Дописать в `.env` webhook-переменные (секрет:
   `python -c "import secrets; print(secrets.token_urlsafe(32))"`):
   ```
   WEBHOOK_BASE_URL=https://<туннель>.ngrok-free.app
   WEBHOOK_SECRET=<случайная строка>
   ```
4. Запустить бота (webhook регистрируется на старте автоматически):
   ```bash
   uv run python app/bot.py
   # или с автоперезапуском:
   watchfiles "uv run app/bot.py"
   ```

Проверить, что webhook встал:
```bash
curl "https://api.telegram.org/bot<ТОКЕН>/getWebhookInfo"
```

URL ngrok на free-плане меняется при каждом перезапуске — тогда обнови
`WEBHOOK_BASE_URL` и перезапусти бота.

## Переменные окружения

Бот регистрирует webhook автоматически при старте (`on_startup`). Cloud Run
подставляет `PORT` сам — сервис слушает именно его.

| Переменная | Обяз. | Назначение |
|---|---|---|
| `BOT_TOKEN` | да | Токен Telegram-бота. |
| `DATABASE_URL` | да | Строка подключения к Postgres (`postgresql+asyncpg://…`). |
| `WEBHOOK_BASE_URL` | да | Публичный URL сервиса Cloud Run (без хвостового пути). |
| `WEBHOOK_PATH` | нет | Путь webhook'а, по умолчанию `/webhook`. |
| `WEBHOOK_SECRET` | реком. | Secret token, который Telegram шлёт в `X-Telegram-Bot-Api-Secret-Token`. |
| `PORT` | нет | Порт HTTP-сервера; задаёт Cloud Run (по умолчанию `8080`). |
| `API_AUDIENCE` | нет | Ожидаемый `aud` OIDC-токена Cloud Tasks (публичный URL API). |
| `TASKS_SERVICE_ACCOUNT_EMAIL` | нет | Email сервисного аккаунта Cloud Tasks. |
| `ADMIN_ID` | нет | Telegram ID администратора (доступ к `/broadcast`). |
| `T_INVEST_TOKEN` | нет | Сервисный T-Invest токен для фоновых задач. |
| `BONDS_SYNC_URL` | нет | Базовый URL сервиса синхронизации облигаций. |

Без `WEBHOOK_BASE_URL` сервис падает на старте с `RuntimeError` — webhook-режим
требует публичного URL.
