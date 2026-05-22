"""
Точка входа FastAPI-приложения (Telegram Mini App API).

Использует существующую инфраструктуру проекта:
- app/config.py      — настройки
- app/database.py    — подключение к БД и get_session()
- app/models/        — все ORM-модели

Запуск (из папки backend/):
    uvicorn app.main:app --reload
"""

from fastapi import FastAPI

from app.api.v1 import auth, profiles, questionnaire, discovery

app = FastAPI(
    title="Friendship App — Mini App API",
    description="API для Telegram Mini App. Авторизация через Telegram initData.",
    version="0.2.0",
)

# --- Роутеры ---
# Все эндпоинты версионированы: /api/v1/...
app.include_router(auth.router, prefix="/api/v1")
app.include_router(profiles.router, prefix="/api/v1")
app.include_router(questionnaire.router, prefix="/api/v1")
app.include_router(discovery.router, prefix="/api/v1")


@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    """Проверка работоспособности сервиса."""
    return {"status": "ok"}
