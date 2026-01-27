FROM python:3.12-slim

WORKDIR /app

# Установка uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Копируем файлы зависимостей
COPY pyproject.toml uv.lock ./

# Устанавливаем зависимости
RUN uv sync --frozen --no-dev

# Копируем код приложения
COPY app/ ./app/

# Запуск бота
CMD ["uv", "run", "python", "app/bot.py"]
