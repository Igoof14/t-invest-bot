# Продуктовая аналитика

Все продуктовые события бота пишутся в одну таблицу Postgres — `bot_events`.
Готового UI нет: метрики считаются SQL-запросами из этого файла.

## Как это работает

Один апдейт от пользователя = одна строка, которую пишет
`AnalyticsMiddleware` (`app/features/analytics/middleware.py`), зарегистрированная
как `dp.update.outer_middleware` в `app/bot.py`. Плюс явные вызовы `track()` в
местах, которые мидлварь увидеть не может: конверсия токена, включение алертов,
исходящие уведомления.

Запись синхронная, внутри обработки апдейта. Это осознанно: Cloud Run
замораживает инстанс между запросами, поэтому «отправить событие в фоне после
ответа» приводило бы к недетерминированной потере данных.

**Инвариант:** сбой аналитики никогда не ломает пользовательский сценарий.
`track()` и репозиторий глотают любое исключение и пишут `WARNING` в лог. Если
что-то пошло не так, у вас будут дырки в данных, но не сломанный бот.

### Аварийный выключатель

```
ANALYTICS_ENABLED=false      # полностью выключить запись событий
ANALYTICS_TRACK_ADMIN=true   # включить трекинг действий админа (для локальной отладки)
```

По умолчанию действия `ADMIN_ID` в аналитику **не попадают**: `/broadcast` и
тестовые прожатия иначе искажают воронку и отчёт по использованию фич.

## Что НЕ хранится

**Текст сообщений не сохраняется никогда.** Через текст проходит T-Invest токен
пользователя (FSM `TokenStates.waiting_for_token`), поэтому у текстовых событий
пишется только `text_len`. В `track()` стоит запрет на ключи `text`, `token`,
`message`, `caption` — они выбрасываются из `props` с предупреждением в лог, и
это поведение закреплено тестом. Не обходите его.

## Схема

```
bot_events
  id           BIGSERIAL PK   -- монотонный курсор для будущего экспорта в BigQuery
  occurred_at  TIMESTAMPTZ    -- время события
  telegram_id  BIGINT NULL    -- NULL у системных событий (broadcast_finished)
  event_name   VARCHAR(64)    -- имя события, см. таблицу ниже
  action       VARCHAR(128)   -- нормализованное действие: callback_data, имя команды, текст кнопки
  direction    VARCHAR(3)     -- 'in' (действие юзера) | 'out' (отправка бота)
  props        JSONB NULL     -- остальные свойства
  latency_ms   INTEGER NULL   -- время обработки апдейта
  exported_at  TIMESTAMPTZ    -- зарезервировано под выгрузку в BigQuery
```

Индексы: `(telegram_id, occurred_at)` — воронка и retention;
`(event_name, occurred_at)` — счётчики по событию; `(occurred_at)` — DAU и
пруннинг. Партиционирования нет: при текущем объёме btree-индексов достаточно,
вернуться стоит примерно на 50 млн строк.

## Таксономия событий

Автоматические (пишет мидлварь, `direction = 'in'`):

| `event_name` | `action` | props |
|---|---|---|
| `command` | имя команды (`start`) | `has_payload`, `matched`, `error`, `is_admin` |
| `callback_click` | полный `callback_data` | `matched`, `error`, `is_admin` |
| `button_click` | текст кнопки reply-клавиатуры | `matched`, `error`, `is_admin` |
| `text_message` | `NULL` | `text_len`, `matched`, `error` |
| `update_other` | тип вложенного объекта | `matched` |

`matched = false` означает, что для апдейта не нашлось хендлера — это прямой
сигнал о тупике в UX (мёртвая кнопка, устаревшее сообщение).

Явные:

| `event_name` | props | Где вызывается |
|---|---|---|
| `bot_start` | `is_new_user`, `has_token`, `source` | `base/handlers.py` |
| `onboarding_step_shown` | `step` | `onboarding/handlers.py` |
| `onboarding_cta_clicked` | — | `onboarding/handlers.py` |
| `token_prompt_shown` | `entry` (`onboarding`/`settings`) | `users/handlers.py` |
| `token_submitted` | `valid` | `users/handlers.py` |
| `token_connected` | — | `users/handlers.py` |
| `token_removed` | — | `users/handlers.py` |
| `bonds_synced` | `count`, `ok` | `users/handlers.py` |
| `events_synced` | `count`, `ok` | `users/handlers.py` |
| `alert_toggled` | `feature`, `enabled`, `agency` | 4 фичи уведомлений |
| `alert_setting_changed` | `feature`, `field`, `value` | `price_monitoring`, `offer_warning` |
| `data_screen_viewed` | `screen`, `items`, `outcome` | `base/handlers.py`, `coupons` |
| `notification_sent` | `kind`, `items` | `common/delivery.py`, `broadcast` |
| `notification_failed` | `kind`, `reason` | `common/delivery.py`, `broadcast` |
| `broadcast_finished` | `delivered`, `blocked`, `failed`, `recipients` | `broadcast/service.py` |

`kind` у исходящих: `price`, `offer`, `rating`, `fns`, `broadcast`.
`reason` у неудач: `blocked` (заблокировал бота), `bad_request`,
`retry_after`, `transport`.

---

## Запросы

### 1. Воронка онбординга

Главная метрика. Когорта — те, кто нажал `/start` за последние 30 дней;
шаги считаются только после их первого `bot_start`.

```sql
WITH cohort AS (
    SELECT telegram_id, min(occurred_at) AS started_at
    FROM bot_events
    WHERE event_name = 'bot_start'
    GROUP BY telegram_id
    HAVING min(occurred_at) >= now() - interval '30 days'
), steps AS (
    SELECT c.telegram_id, c.started_at,
        min(e.occurred_at) FILTER (WHERE e.event_name = 'onboarding_cta_clicked') AS cta,
        min(e.occurred_at) FILTER (WHERE e.event_name = 'token_prompt_shown')     AS prompt,
        min(e.occurred_at) FILTER (WHERE e.event_name = 'token_submitted')        AS submitted,
        min(e.occurred_at) FILTER (WHERE e.event_name = 'token_connected')        AS connected,
        min(e.occurred_at) FILTER (WHERE e.event_name = 'alert_toggled'
                                    AND e.props->>'enabled' = 'true')            AS alert_on,
        min(e.occurred_at) FILTER (WHERE e.event_name = 'notification_sent')      AS first_notify
    FROM cohort c
    LEFT JOIN bot_events e
           ON e.telegram_id = c.telegram_id
          AND e.occurred_at >= c.started_at
    GROUP BY c.telegram_id, c.started_at
)
SELECT count(*)            AS started,
       count(cta)          AS clicked_connect,
       count(prompt)       AS saw_instruction,
       count(submitted)    AS submitted_token,
       count(connected)    AS token_connected,
       count(alert_on)     AS enabled_first_alert,
       count(first_notify) AS got_first_notification,
       round(100.0 * count(connected) / nullif(count(*), 0), 1)          AS start_to_token_pct,
       round(100.0 * count(connected) / nullif(count(submitted), 0), 1)  AS token_valid_pct,
       round(avg(extract(epoch FROM connected - started_at)) / 60, 1)    AS avg_min_to_token
FROM steps;
```

Качество ввода токена — сколько попыток отваливается на невалидном токене:

```sql
SELECT count(*) FILTER (WHERE (props->>'valid')::bool)     AS valid_attempts,
       count(*) FILTER (WHERE NOT (props->>'valid')::bool) AS invalid_attempts,
       count(DISTINCT telegram_id)                          AS users_tried
FROM bot_events
WHERE event_name = 'token_submitted'
  AND occurred_at >= now() - interval '30 days';
```

### 2. Воронка по источнику привлечения

`source` — deep-link payload из `t.me/<bot>?start=<payload>`, нормализованный
`sanitize_source()`. First-touch берётся из самого первого `bot_start`
пользователя.

```sql
WITH first_touch AS (
    SELECT DISTINCT ON (telegram_id)
           telegram_id,
           coalesce(props->>'source', '(direct)') AS source,
           occurred_at AS started_at
    FROM bot_events
    WHERE event_name = 'bot_start'
    ORDER BY telegram_id, occurred_at
), activated AS (
    SELECT DISTINCT telegram_id FROM bot_events WHERE event_name = 'token_connected'
)
SELECT f.source,
       count(*)                                                        AS users,
       count(a.telegram_id)                                            AS activated,
       round(100.0 * count(a.telegram_id) / nullif(count(*), 0), 1)     AS activation_pct
FROM first_touch f
LEFT JOIN activated a USING (telegram_id)
WHERE f.started_at >= now() - interval '90 days'
GROUP BY f.source
ORDER BY users DESC;
```

### 3. Retention по когортам дня

```sql
WITH cohort AS (
    SELECT telegram_id,
           (min(occurred_at) AT TIME ZONE 'Europe/Moscow')::date AS cohort_day
    FROM bot_events
    WHERE direction = 'in' AND telegram_id IS NOT NULL
    GROUP BY telegram_id
), act AS (
    SELECT DISTINCT telegram_id,
           (occurred_at AT TIME ZONE 'Europe/Moscow')::date AS day
    FROM bot_events
    WHERE direction = 'in'
)
SELECT c.cohort_day,
       count(DISTINCT c.telegram_id) AS cohort_size,
       count(DISTINCT a.telegram_id) FILTER (
           WHERE a.day BETWEEN c.cohort_day + 1 AND c.cohort_day + 1)  AS d1,
       count(DISTINCT a.telegram_id) FILTER (
           WHERE a.day BETWEEN c.cohort_day + 1 AND c.cohort_day + 7)  AS d1_7,
       count(DISTINCT a.telegram_id) FILTER (
           WHERE a.day BETWEEN c.cohort_day + 1 AND c.cohort_day + 30) AS d1_30
FROM cohort c
LEFT JOIN act a ON a.telegram_id = c.telegram_id
WHERE c.cohort_day BETWEEN current_date - 90 AND current_date - 1
GROUP BY c.cohort_day
ORDER BY c.cohort_day DESC;
```

Осторожно: у когорт младше 7 и 30 дней колонки `d1_7`/`d1_30` структурно
неполные — читайте их только для достаточно старых когорт.

### 4. DAU / WAU / MAU

```sql
SELECT count(DISTINCT telegram_id) FILTER (WHERE occurred_at >= current_date)      AS dau,
       count(DISTINCT telegram_id) FILTER (WHERE occurred_at >= current_date - 6)  AS wau,
       count(DISTINCT telegram_id) FILTER (WHERE occurred_at >= current_date - 29) AS mau,
       round(100.0 * count(DISTINCT telegram_id) FILTER (WHERE occurred_at >= current_date)
             / nullif(count(DISTINCT telegram_id)
                      FILTER (WHERE occurred_at >= current_date - 29), 0), 1) AS stickiness_pct
FROM bot_events
WHERE direction = 'in' AND occurred_at >= current_date - 29;
```

По дням:

```sql
SELECT (occurred_at AT TIME ZONE 'Europe/Moscow')::date AS day,
       count(DISTINCT telegram_id) AS dau,
       count(*)                    AS updates
FROM bot_events
WHERE direction = 'in' AND occurred_at >= current_date - 29
GROUP BY 1 ORDER BY 1 DESC;
```

### 5. Исходящие vs входящие

Скольким уникальным юзерам бот написал, сколько из них проявили активность в
следующие 24 часа, сколько заблокировало бота.

```sql
WITH sent AS (
    SELECT telegram_id, occurred_at, props->>'kind' AS kind
    FROM bot_events
    WHERE event_name = 'notification_sent'
      AND occurred_at >= now() - interval '30 days'
)
SELECT s.kind,
       count(*)                      AS notifications,
       count(DISTINCT s.telegram_id) AS users_reached,
       count(*) FILTER (WHERE EXISTS (
           SELECT 1 FROM bot_events r
           WHERE r.telegram_id = s.telegram_id
             AND r.direction = 'in'
             AND r.occurred_at >  s.occurred_at
             AND r.occurred_at <= s.occurred_at + interval '24 hours'
       )) AS followed_by_activity_24h,
       round(100.0 * count(*) FILTER (WHERE EXISTS (
           SELECT 1 FROM bot_events r
           WHERE r.telegram_id = s.telegram_id
             AND r.direction = 'in'
             AND r.occurred_at >  s.occurred_at
             AND r.occurred_at <= s.occurred_at + interval '24 hours'
       )) / nullif(count(*), 0), 1) AS response_rate_pct
FROM sent s
GROUP BY s.kind
ORDER BY notifications DESC;
```

Здоровье доставки:

```sql
SELECT props->>'kind' AS kind,
       count(*) FILTER (WHERE event_name = 'notification_sent')   AS sent,
       count(*) FILTER (WHERE event_name = 'notification_failed') AS failed,
       count(*) FILTER (WHERE props->>'reason' = 'blocked')       AS blocked,
       count(*) FILTER (WHERE props->>'reason' = 'retry_after')   AS flood_limited,
       count(*) FILTER (WHERE props->>'reason' = 'transport')     AS transport_errors
FROM bot_events
WHERE event_name IN ('notification_sent', 'notification_failed')
  AND occurred_at >= now() - interval '7 days'
GROUP BY 1 ORDER BY sent DESC;
```

### 6. Использование фич и мёртвые разделы

```sql
SELECT action,
       count(*)                    AS clicks,
       count(DISTINCT telegram_id) AS users,
       max(occurred_at)::date      AS last_used,
       round(avg(latency_ms))      AS avg_latency_ms
FROM bot_events
WHERE direction = 'in'
  AND action IS NOT NULL
  AND occurred_at >= current_date - 29
GROUP BY action
ORDER BY users DESC;
```

Разделы хаба «Уведомления» отдельно (у них `action` вида `menu:<section>:open`):

```sql
SELECT split_part(action, ':', 2)   AS section,
       split_part(action, ':', 3)   AS what,
       count(DISTINCT telegram_id)  AS users,
       count(*)                     AS clicks
FROM bot_events
WHERE event_name = 'callback_click'
  AND action LIKE 'menu:%'
  AND occurred_at >= current_date - 29
GROUP BY 1, 2 ORDER BY users DESC;
```

Тупики в UX — апдейты, для которых не нашлось хендлера. Фильтр по именам
обязателен: `matched` есть только у автоматических событий, без него в выборку
попадут все явные.

```sql
SELECT event_name,
       coalesce(action, '(текст)')  AS what,
       count(*)                     AS updates,
       count(DISTINCT telegram_id)  AS users
FROM bot_events
WHERE event_name IN ('command', 'callback_click', 'button_click', 'text_message', 'update_other')
  AND props->>'matched' = 'false'
  AND occurred_at >= current_date - 13
GROUP BY 1, 2 ORDER BY updates DESC;
```

Ошибки в хендлерах:

```sql
SELECT action, count(*) AS errors, count(DISTINCT telegram_id) AS users
FROM bot_events
WHERE props->>'error' = 'true' AND occurred_at >= current_date - 6
GROUP BY 1 ORDER BY errors DESC;
```

Проникновение фич — кто включил какие уведомления:

```sql
SELECT props->>'feature' AS feature,
       count(DISTINCT telegram_id) FILTER (WHERE (props->>'enabled')::bool)     AS enabled_by,
       count(DISTINCT telegram_id) FILTER (WHERE NOT (props->>'enabled')::bool) AS disabled_by
FROM bot_events
WHERE event_name = 'alert_toggled'
GROUP BY 1 ORDER BY enabled_by DESC;
```

### 7. Отток

```sql
SELECT date_trunc('week', occurred_at)::date AS week,
       props->>'kind'                        AS kind,
       count(DISTINCT telegram_id)           AS users_blocked
FROM bot_events
WHERE event_name = 'notification_failed' AND props->>'reason' = 'blocked'
GROUP BY 1, 2 ORDER BY week DESC;
```

Успевали ли отвалившиеся активироваться:

```sql
WITH blocked AS (
    SELECT DISTINCT ON (telegram_id) telegram_id, occurred_at AS blocked_at
    FROM bot_events
    WHERE event_name = 'notification_failed' AND props->>'reason' = 'blocked'
    ORDER BY telegram_id, occurred_at
), started AS (
    SELECT telegram_id, min(occurred_at) AS started_at
    FROM bot_events WHERE event_name = 'bot_start' GROUP BY telegram_id
)
SELECT count(*) AS churned,
       round(percentile_cont(0.5) WITHIN GROUP (
           ORDER BY extract(epoch FROM b.blocked_at - s.started_at) / 86400
       )::numeric, 1) AS median_days_to_block,
       count(*) FILTER (WHERE EXISTS (
           SELECT 1 FROM bot_events e
           WHERE e.telegram_id = b.telegram_id AND e.event_name = 'token_connected'
       )) AS was_activated
FROM blocked b JOIN started s USING (telegram_id);
```

---

## Эксплуатация

Размер таблицы:

```sql
SELECT pg_size_pretty(pg_total_relation_size('bot_events')) AS total,
       count(*) AS rows,
       min(occurred_at) AS oldest
FROM bot_events;
```

**Политика хранения — 400 дней** (год плюс запас на сравнение год к году).
Пруннинг ручной, раз в квартал; автоматизировать нечем, пока в проекте нет
планировщика:

```sql
DELETE FROM bot_events WHERE occurred_at < now() - interval '400 days';
```

**Ограничение схемы.** Таблицы создаются через `Base.metadata.create_all`
(`app/core/database.py`), Alembic в проекте нет. `create_all` умеет добавлять
таблицы, но не изменять колонки: любое изменение схемы `bot_events` потребует
ручного `ALTER TABLE` на проде. Поэтому переменные атрибуты событий живут в
`props`, а не в колонках — в частности, источник привлечения не стал колонкой
`bot_users.source`.

**Курсор будущего экспорта в BigQuery.** `id` монотонен, `exported_at`
зарезервирован:

```sql
SELECT * FROM bot_events WHERE id > :last_exported_id ORDER BY id LIMIT 50000;
```
