#!/bin/sh
# =============================================================================
# entrypoint.sh — точка входа API-контейнера.
#
# Порядок запуска важен:
#   1. Ждать БД  — PostgreSQL стартует дольше, чем контейнер становится healthy.
#                  Без ожидания alembic упадёт с "connection refused".
#   2. Миграции  — создают/обновляют схему. Idempotent: можно запускать повторно.
#   3. Seed      — наполняют справочники (интересы, достижения). Idempotent.
#   4. Старт API — только после того, как БД готова и данные на месте.
#
# Бот запускается отдельным сервисом без этого entrypoint — ему миграции
# и seed не нужны (только читает/пишет данные через shared БД).
# =============================================================================

set -e  # Остановить скрипт при любой ошибке (не молчать о падениях)

echo "==> [1/4] Ожидание PostgreSQL..."
# Пробуем подключиться до 30 раз с интервалом 2 сек (итого 60 сек).
# pg_isready встроен в образ python если установлен psycopg2, но у нас asyncpg.
# Используем python-проверку через asyncpg напрямую — не требует доп. утилит.
MAX_RETRIES=30
RETRY=0
until python -c "
import asyncio, asyncpg, os, sys
async def check():
    url = os.environ.get('DATABASE_URL', '')
    # asyncpg принимает DSN без +asyncpg префикса
    dsn = url.replace('postgresql+asyncpg://', 'postgresql://')
    try:
        conn = await asyncpg.connect(dsn, timeout=3)
        await conn.close()
    except Exception as e:
        sys.exit(1)
asyncio.run(check())
" 2>/dev/null; do
    RETRY=$((RETRY + 1))
    if [ "$RETRY" -ge "$MAX_RETRIES" ]; then
        echo "ОШИБКА: PostgreSQL не поднялся за 60 секунд. Проверьте DATABASE_URL и healthcheck postgres."
        exit 1
    fi
    echo "  PostgreSQL не готов, жду... ($RETRY/$MAX_RETRIES)"
    sleep 2
done
echo "  PostgreSQL готов."

echo "==> [2/4] Применение миграций (alembic upgrade head)..."
alembic upgrade head
echo "  Миграции применены."

echo "==> [3/4] Seed справочников..."
python -m app.scripts.seed_interests
python -m app.scripts.seed_achievements
echo "  Seed завершён."

echo "==> [4/4] Запуск API (uvicorn)..."
# "$@" позволяет переопределить команду из docker-compose command:
# Если command: не задан — запускается CMD из Dockerfile.
exec "$@"
