"""
REST-эндпоинт модуля «Достижения».

  GET /api/v1/achievements/me  — витрина достижений текущего пользователя
                                 (полученные + ещё закрытые с датами).

Роутер — тонкий: собирает сервис через Depends и отдаёт готовую схему.
Выдача достижений здесь НЕ делается — она происходит автоматически в местах
событий (создание компании, мэтч). Этот роутер только читает.

Префикс: внутренний `/achievements`, внешний `/api/v1` навешивается в main.py —
как у discovery / groups.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_session
from app.models.user import User
from app.repositories.achievement_repository import AchievementRepository
from app.schemas.achievements import AchievementShowcase
from app.services.achievement_service import AchievementService

router = APIRouter(prefix="/achievements", tags=["achievements"])


def get_achievement_service(
    session: AsyncSession = Depends(get_session),
) -> AchievementService:
    """Собрать сервис достижений с его репозиторием (сессию подставляет FastAPI)."""
    return AchievementService(repo=AchievementRepository(session))


@router.get("/me", response_model=AchievementShowcase)
async def get_my_achievements(
    current_user: User = Depends(get_current_user),
    service: AchievementService = Depends(get_achievement_service),
) -> AchievementShowcase:
    """
    Витрина достижений текущего пользователя.

    Отдаёт весь справочник: полученные помечены earned=True с датой, остальные —
    закрытые цели. Новые достижения, добавленные в seed, появятся здесь сами.
    """
    return await service.get_showcase(user_id=current_user.id)
