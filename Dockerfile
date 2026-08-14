FROM python:3.12-slim

# T-Invest отдаётся под «Русским доверенным корневым CA», которого нет ни в одном
# системном хранилище. SDK везёт этот корень с собой и подставляет его только при
# SSL_TBANK_VERIFY=true — без этого каждый вызов брокера падает на TLS handshake.
ENV SSL_TBANK_VERIFY=true

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev


# Копируем код приложения
COPY app/ ./app/

# Запуск бота
CMD ["uv", "run", "python", "app/bot.py"]
