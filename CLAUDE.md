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

The price monitoring pipeline (`app/invest/price_monitor.py` + `app/services/price_alert_service.py`):
1. Hourly: fetches bond prices for all users with alerts enabled
2. Compares against previous snapshot stored in `bond_price_history` table
3. Detects anomalies using per-user thresholds (drop/rise warning/critical)
4. Anti-spam: 4-hour cooldown per bond per alert type, max 10 alerts/day per user
5. If >3 anomalies, aggregates into a single summary message

### FSM States

Aiogram FSM is used in `app/handlers/setting_handlers.py` for multi-step flows:
- `TokenStates` - token input and deletion confirmation
- `ThresholdStates` - sequential input of 4 threshold values (drop warning/critical, rise warning/critical)

### Scheduled Tasks (Moscow Time)

- Daily coupon report: 18:10 every day
- Weekly coupon report: 18:10 every Friday
- Price anomaly check: hourly 10:00-18:00 Mon-Fri

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
