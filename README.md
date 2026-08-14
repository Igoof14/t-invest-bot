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
| `ANALYTICS_ENABLED` | нет | Запись продуктовых событий в `bot_events`. По умолчанию `true`; `false` — аварийный выключатель без деплоя кода. |
| `ANALYTICS_TRACK_ADMIN` | нет | Трекать ли действия `ADMIN_ID`. По умолчанию `false`, чтобы `/broadcast` и тестовые прожатия не искажали воронку. |
| `T_INVEST_TOKEN` | нет | Сервисный T-Invest токен для фоновых задач. |
| `SSL_TBANK_VERIFY` | нет | Использовать «Русский доверенный корневой CA», который SDK везёт с собой. По умолчанию `true`; выключать нельзя — иначе любой вызов T-Invest падает на TLS handshake. |
| `BONDS_SYNC_URL` | нет | Базовый URL сервиса синхронизации облигаций. |
| `BACKEND_URL` | да | Базовый URL приватного Cloud Run сервиса `backend` (без пути), например `https://backend-iyvjwivbpq-ey.a.run.app`. Он же audience OIDC id-token'а. Loopback-адрес (`http://127.0.0.1:8000`) отключает OIDC-авторизацию — см. ниже. |
| `MINIAPP_URL` | нет | Публичный HTTPS-адрес мини-аппа. Пока не задан, кнопки «Открыть приложение» в меню нет. |
| `MINIAPP_ORIGIN` | нет | Origin, которому разрешён CORS к `/miniapp/api` (например `http://localhost:5173`). Пусто — заголовки CORS не выставляются. |
| `MINIAPP_DEV_TELEGRAM_ID` | нет | **Только для разработки.** Запрос к `/miniapp/api` без подписи Telegram считается запросом этого пользователя. В проде задавать нельзя — API окажется открыт всем. |

Запросы к облачному `backend` авторизуются OIDC id-token'ом: он берётся у
metadata server (в Cloud Run) или из application default credentials и
кэшируется до истечения срока. Сервис-аккаунту бота нужна роль
`roles/run.invoker` на сервисе `backend`. Для облачного бэкенда локально нужны
credentials сервис-аккаунта — пользовательские ADC id-token не выдают:

```bash
gcloud auth application-default login \
  --impersonate-service-account=772435034855-compute@developer.gserviceaccount.com
```

Без них бот пишет в лог понятную ошибку и отвечает «Не удалось получить данные
об офертах», а не падает внутри HTTP-клиента.

### Локальный бэкенд

Если `BACKEND_URL` указывает на loopback-хост (`127.0.0.1`, `localhost`, `::1`),
бот не запрашивает id-token и шлёт запросы без заголовка `Authorization` —
`gcloud auth application-default login` не нужен. Достаточно одной строки
в `.env`:

```
BACKEND_URL=http://127.0.0.1:8000
```

Прод это не затрагивает: URL Cloud Run всегда публичный https-домен.

### Mini App

`app/features/miniapp` — BFF для Telegram Mini App (фронтенд лежит в
`bondelo-miniapp`). Роуты живут под `/miniapp/api`, каждый запрос обязан нести
заголовок `Authorization: tma <initData>`: подпись проверяется токеном бота, и
`telegram_id` берётся только из неё. Бэкенд принимает id прямо в пути и не
аутентифицирует вызывающего, поэтому напрямую из браузера к нему обращаться
нельзя.

Для разработки фронтенда полный бот не нужен — он работает по webhook и требует
туннеля. Достаточно поднять только BFF:

```
BACKEND_URL=http://127.0.0.1:8000     # loopback: запросы идут без OIDC
MINIAPP_ORIGIN=http://localhost:5173
MINIAPP_DEV_TELEGRAM_ID=<ваш telegram id>
```

```bash
uv run python app/miniapp_dev.py
```

Сервер слушает `127.0.0.1:8080` — тот же порт, что и боевой сервис, поэтому
dev-сервер Vite настраивать не нужно. Без `MINIAPP_DEV_TELEGRAM_ID` запросы без
подписи Telegram отклоняются с 401.

Без `WEBHOOK_BASE_URL` сервис падает на старте с `RuntimeError` — webhook-режим
требует публичного URL.

## Продуктовая аналитика

События пишутся в таблицу `bot_events`. Таксономия событий, готовые SQL-запросы
(воронка онбординга, retention, DAU/WAU/MAU, охват уведомлений, использование
фич, отток) и политика хранения — в [docs/analytics.md](docs/analytics.md).
