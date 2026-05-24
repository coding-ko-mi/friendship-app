"""
REST-эндпоинт витрины достижений (геймификация).

  GET /api/v1/me/achievements — весь справочник достижений с флагом earned
                                для текущего пользователя.

Почему весь справочник, а не только полученные: витрине нужен UX «прогресс +
что ещё можно получить» — пользователь видит и открытые, и закрытые достижения.
Это ядро петли вовлечённости. Один эндпоинт закрывает оба сценария: фронт сам
решает, как показать (полученные ярко, остальные тускло).

Роутер — тонкий: собирает сервис через Depends и отдаёт готовую схему. Доменных
ошибок здесь нет (справочник всегда доступен, пользователь — из JWT), поэтому
маппинг ошибок как в groups_router не нужен.

Префикс: внутренний пуст, внешний `/api/v1` навешивается в main.py (как у
profiles: путь получается /api/v1/me/achievements). Соседи (profiles) объявляют
роутер без префикса и пути вида "/me/...", делаем так же.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

# Зависимости из ядра/БД — те же, что используют profiles и groups_router.
from app.api.deps import get_current_user
from app.database import get_session
from app.models.user import User
from app.repositories.achievement_repository import AchievementRepository
from app.schemas.achievements import AchievementsResponse
from app.services.achievement_service import AchievementService

router = APIRouter(tags=["achievements"])


def get_achievement_service(
    session: AsyncSession = Depends(get_session),
) -> AchievementService:
    """
    Собрать AchievementService с его репозиторием.

    Сервис не знает, откуда берётся session — её подставляет FastAPI. Так сервис
    остаётся тестируемым (в тестах подставим фейковый репозиторий).
    """
    return AchievementService(achievement_repo=AchievementRepository(session))


@router.get("/me/achievements", response_model=AchievementsResponse)
async def get_my_achievements(
    current_user: User = Depends(get_current_user),
    service: AchievementService = Depends(get_achievement_service),
) -> AchievementsResponse:
    """
    Витрина достижений текущего пользователя.

    Возвращает весь справочник: по каждому достижению — получено оно или нет
    (earned) и когда (earned_at). Плюс сводка earned_count / total для «3 из 8».
    """
    return await service.get_showcase(current_user.id)
