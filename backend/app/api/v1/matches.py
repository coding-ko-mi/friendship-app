"""
REST-эндпоинт списка мэтчей текущего пользователя.

  GET /api/v1/matches — все взаимные лайки текущего пользователя со вторым
                        участником пары (для экрана «Матчи» в Mini App).

Роутер — тонкий: достаём мэтчи через MatchingRepository и собираем карточки.
Тяжёлой бизнес-логики здесь нет (это просто список), поэтому отдельный сервис
не заводим — это идиоматично с тонкими роутерами проекта (см. interests.py).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_session
from app.models.user import User
from app.repositories.matching_repository import MatchingRepository
from app.schemas.matching import MatchCard

router = APIRouter(tags=["matches"])


@router.get("/matches", response_model=list[MatchCard])
async def list_my_matches(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[MatchCard]:
    """
    Все мэтчи текущего пользователя (для экрана «Матчи»).

    Возвращает по каждому мэтчу: id мэтча, данные собеседника (id/имя/возраст/
    фото) и время создания мэтча. Сортировка: свежие сверху.
    """
    repo = MatchingRepository(session)
    pairs = await repo.list_user_matches(current_user.id)
    return [
        MatchCard(
            match_id=match.id,
            user_id=other.id,
            name=other.name,
            age=other.age,
            photo_file_id=other.photo_file_id,
            matched_at=match.created_at,
        )
        for match, other in pairs
    ]
