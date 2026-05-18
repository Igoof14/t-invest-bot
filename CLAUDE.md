# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Telegram bot (Bondelo) for T-Invest bond portfolio management. Built with aiogram 3.x, SQLAlchemy 2.x async, and PostgreSQL.

## Commands

```bash
# Run locally with auto-reload
watchfiles "uv run app/bot.py"

# Start local PostgreSQL
docker compose -f docker-compose.local.yml up -d

# Lint and format
uv run ruff check --fix .
uv run ruff format .

# Type check
uv run pyright

# Install dependencies
uv sync

# Production build
docker compose up -d --build
```

No test suite exists yet.

## Architecture

### Entry Point
`app/bot.py` - Initializes bot, database, registers handlers, starts APScheduler jobs, and runs polling.

### Core Modules

- **app/core/** - Configuration (Pydantic settings), database engine/session management, enums for UI text
- **app/models/** - SQLAlchemy models: BotUser, TinvestUser, UserAlertSettings, BondPriceHistory, PriceAlertSent
- **app/handlers/** - Aiogram message/callback handlers organized by feature (base, coupon, settings)
- **app/services/** - Scheduled tasks: daily/weekly coupon reports, hourly price anomaly checks
- **app/invest/** - T-Invest API client and bond portfolio operations
- **app/storage/** - Database CRUD operations (repositories)
- **app/keyboards/** - Telegram inline/reply keyboard builders

### Data Flow

1. User sends message/callback -> Handler processes request
2. Handler calls storage layer for user data
3. Handler calls invest module for T-Invest API data
4. Handler builds response using keyboards and enums
5. Scheduled services run independently via APScheduler

### Handler Registration

All handlers are registered centrally in `app/handlers/registration.py`. It wires aiogram message filters (matching `ButtonTexts` enum values) and callback query filters (matching `CallbackData` enum prefixes) to handler functions. New features must be registered here.

### T-Invest API Client

`app/invest/tbank_client.py` is an async context manager wrapping aiohttp. It uses POST requests to T-Invest REST API with automatic retry (3x for 5xx errors) and SSL via certifi. All API interaction flows through this client. Token is passed per-user from the database.

### Price Alert System

The price monitoring feature is split into three layers:

- **`app/invest/portfolio_prices.py`** — `fetch_portfolio_bond_prices(token, bonds_cache)` returns current `BondPrice` snapshots from T-Invest API. Pure API layer, no DB.
- **`app/storage/price_alert/`** — three focused repositories:
  - `AlertSettingsRepository` (user alert preferences)
  - `PriceHistoryRepository` (price snapshots, returns domain `BondPrice` not ORM)
  - `SentAlertRepository` (anti-spam ledger)
  Plus `session_scope()` helper and a legacy `PriceAlertStorage` facade kept for backward compatibility with handlers.
- **`app/services/price_alert/`** — the feature package itself:
  - `domain.py` — `AlertType`, `AlertSeverity`, `AlertDirection`, `PriceAnomaly` (frozen dataclasses with `is_critical` / `is_drop` properties)
  - `config.py` — `AlertPolicyConfig` (cooldown, daily limit, aggregation thresholds) and `AlertThresholds` (per-user drop/rise warning/critical, built from `PriceAlertSettings`)
  - `detector.py` — pure `detect_anomalies(current, previous, thresholds)` function
  - `anti_spam.py` — `AntiSpamPolicy` with cooldown, daily limit and WARNING→CRITICAL escalation in the same direction (drop/rise)
  - `formatter.py` — pure `format_single_alert` and `format_aggregated_alert`
  - `notifier.py` — `PriceAlertNotifier` sends messages and records them via `SentAlertRepository`
  - `service.py` — `PriceAlertService` orchestrator that wires everything via constructor DI; static `check_price_anomalies(bot)` and `run_daily_cleanup(bot)` are scheduler entry points

Runtime flow per check:
1. Hourly job: fetch users with alerts enabled, load bonds cache once, iterate users.
2. For each user: fetch token → fetch current prices → load previous snapshot → `detect_anomalies` against `AlertThresholds.from_settings(settings)`.
3. Anomalies pass through `AntiSpamPolicy.filter` (4h cooldown per bond, max 10/day, WARNING→CRITICAL escalation allowed).
4. If filtered count > `aggregate_threshold` (default 3) → aggregated summary message; otherwise individual messages.
5. Notifier sends and records sent alerts in DB.
6. Save current prices as new snapshot.

A separate daily cleanup job (4:00 MSK) deletes price history and sent-alert rows older than 7 days via `PriceAlertService.run_daily_cleanup`.

### FSM States

Aiogram FSM is used in `app/handlers/setting_handlers.py` for multi-step flows:
- `TokenStates` - token input and deletion confirmation
- `ThresholdStates` - sequential input of 4 threshold values (drop warning/critical, rise warning/critical)

### Scheduled Tasks (Moscow Time)

- Daily coupon report: 18:10 every day
- Weekly coupon report: 18:10 every Friday
- Price anomaly check: hourly 10:00-20:00 every day
- Old data cleanup (price history + sent alerts): 04:00 every day

### UI Text

All user-facing text is in Russian and centralized in `app/core/enums.py` via `ButtonTexts` and `Messages` enums. Callback data strings are in `CallbackData` enum.

## Configuration

Required environment variables (see `.env.example`):
- `BOT_TOKEN` - Telegram bot token
- `DATABASE_URL` - PostgreSQL connection string (default: `postgresql+asyncpg://postgres:postgres@localhost:5432/tinvest`)

## Deployment

GitHub Actions (`.github/workflows/deploy.yml`) builds and pushes Docker image to `ghcr.io` on every push to main. Production runs via Docker Compose with Watchtower for auto-updates.

## Code Style

- Line length: 100 characters
- Formatter/linter: ruff with docstring rules enabled (D)
- Type checker: pyright in basic mode
- All database and API operations must be async
- Use context managers for API client sessions
- T-Invest API monetary values use `units + nano` format (see `MoneyValue.to_float()` in `app/invest/models.py`)
