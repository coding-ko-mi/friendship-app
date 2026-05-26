# =============================================================================
# Dockerfile — единый образ для API (uvicorn) и бота (aiogram).
#
# Почему один образ: API и бот используют одни зависимости (SQLAlchemy,
# aiogram, redis и т.д.). Одна сборка = меньше времени на CI и места на диске.
# Разница между сервисами — только команда запуска (command: в compose).
#
# Запуск через docker-compose.yml (см. корень проекта):
#   api-сервис: uvicorn app.main:app ...
#   bot-сервис: python -m app.bot.main
# =============================================================================

# ---- Стадия сборки зависимостей ----
# python:3.11-slim — минимальный образ, не тащит лишнее.
FROM python:3.11-slim AS builder

WORKDIR /build

# Копируем только requirements.txt сначала — docker кэширует этот слой.
# Если код изменился, но зависимости нет — pip install не перезапускается.
COPY requirements.txt .

# --no-cache-dir: не хранить кэш pip внутри образа (экономит ~50 МБ).
# Устанавливаем в /install — потом копируем в финальный образ.
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ---- Финальный образ ----
FROM python:3.11-slim

# Безопасность: не запускаем процессы от root.
# appuser не имеет sudo и shell — минимальные привилегии.
RUN useradd --no-create-home --shell /bin/false appuser

WORKDIR /app

# Копируем установленные зависимости из builder-стадии.
COPY --from=builder /install /usr/local

# Копируем весь код приложения.
# .dockerignore должен исключать: .env, __pycache__, .git, dist, node_modules.
COPY . .

# Гарантируем, что entrypoint.sh исполняемый. Файл добавляли в репозиторий
# с Windows-машины (NTFS не знает unix-бита +x) — без этого chmod контейнер
# падает с "permission denied" на entrypoint.sh при старте.
RUN chmod +x /app/entrypoint.sh

# Меняем владельца файлов на appuser — не root.
RUN chown -R appuser:appuser /app

USER appuser

# Переменные среды по умолчанию (переопределяются через .env в compose).
# PYTHONUNBUFFERED=1: вывод логов сразу, без буферизации (видно в docker logs).
# PYTHONDONTWRITEBYTECODE=1: не создавать .pyc-файлы (чище образ).
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Порт документируем для ясности (реальный bind — в compose через ports:).
EXPOSE 8000

# Команда по умолчанию — API. Бот переопределяет через command: в compose.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
