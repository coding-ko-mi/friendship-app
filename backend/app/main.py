"""
Точка входа FastAPI-приложения (КО МИ — Mini App API).

Использует существующую инфраструктуру проекта:
- app/config.py      — настройки
- app/database.py    — подключение к БД и get_session()
- app/models/        — все ORM-модели

Запуск (из папки backend/):
    uvicorn app.main:app --reload
"""

from fastapi import FastAPI

from app.api.v1 import (
    achievements,
    admin,
    auth,
    discovery,
    groups,
    history,
    interests,
    matches,
    photo,
    profiles,
    questionnaire,
    registration,
)

app = FastAPI(
    title="КО МИ — Mini App API",
    description="API для Telegram Mini App. Авторизация через Telegram initData.",
    version="0.4.0",
)

# --- Роутеры ---
# Все эндпоинты версионированы: /api/v1/...
app.include_router(auth.router, prefix="/api/v1")
app.include_router(profiles.router, prefix="/api/v1")
app.include_router(questionnaire.router, prefix="/api/v1")
app.include_router(discovery.router, prefix="/api/v1")
# Компании + голосование: два роутера (разные пути /groups и /requests).
app.include_router(groups.groups_router, prefix="/api/v1")
app.include_router(groups.requests_router, prefix="/api/v1")
# Достижения (витрина).
app.include_router(achievements.router, prefix="/api/v1")
# Гибридная регистрация: фото из бота + анкета из Mini App.
app.include_router(registration.router, prefix="/api/v1")
# Справочник интересов (онбординг Mini App).
app.include_router(interests.router, prefix="/api/v1")
# Прокси Telegram-фото по file_id (для <img> в Mini App).
app.include_router(photo.router, prefix="/api/v1")
# Список мэтчей текущего пользователя (экран «Матчи»).
app.include_router(matches.router, prefix="/api/v1")
# История лайков + откат лайка (экран «История»).
app.include_router(history.router, prefix="/api/v1")
# Админ-метрики (доступ только для ADMIN_TELEGRAM_ID).
app.include_router(admin.router, prefix="/api/v1")


@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    """Проверка работоспособности сервиса."""
    return {"status": "ok"}
