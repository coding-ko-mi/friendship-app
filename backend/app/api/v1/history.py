"""
REST-эндпоинты экрана «История» (лайкнутые пользователи).

  GET    /api/v1/history                     — список лайкнутых пользователей
  DELETE /api/v1/history/{target_user_id}    — убрать лайк (откатить решение)

ВАЖНО (продуктовое решение): «История» — это ТОЛЬКО лайки из таблицы likes.
Скипы сейчас хранятся в Redis с TTL и в БД не пишутся (см. SkipRepository),
поэтому их в истории нет. Если когда-нибудь решим хранить скипы постоянно —
сюда добавится отдельный список.

Удаление лайка возвращает кандидата в ленту мэтчинга: при следующем feed()
он не будет в excluded_ids (см. MatchingService.get_feed → liked_ids).
Мэтч (если был) при этом НЕ удаляем — это отдельная сущность.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_session
from app.models.user import User
from app.repositories.matching_repository import MatchingRepository
from app.schemas.matching import LikedUserCard

router = APIRouter(tags=["history"])


@router.get("/history", response_model=list[LikedUserCard])
async def list_my_history(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[LikedUserCard]:
    """
    Список людей, которых текущий пользователь лайкнул.

    Сортировка: свежие сверху. Забаненные пользователи отфильтрованы (нет
    смысла их показывать — UI не предложит ничего полезного).
    """
    repo = MatchingRepository(session)
    rows = await repo.list_likes_from(current_user.id)
    return [
        LikedUserCard(
            target_user_id=user.id,
            name=user.name,
            age=user.age,
            photo_file_id=user.photo_file_id,
            liked_at=liked_at,
        )
        for user, liked_at in rows
    ]


@router.delete(
    "/history/{target_user_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_like(
    target_user_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    """
    Убрать лайк, ранее поставленный пользователю target_user_id.

    Только сам лайк — связанный мэтч (если есть) НЕ трогаем (см. док. модуля).
    Skip-метки в Redis тоже не трогаем — это отдельный TTL-кэш, не история.
    """
    if target_user_id == current_user.id:
        # Дешёвая защита: на себя лайков нет в принципе (CHECK в БД), но даём
        # понятную доменную ошибку до запроса.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя убрать лайк самому себе",
        )

    repo = MatchingRepository(session)
    removed = await repo.delete_like(
        from_user_id=current_user.id, to_user_id=target_user_id
    )
    if removed == 0:
        # Идемпотентность не нужна: явный 404 помогает фронту понять,
        # что состояние списка устарело (синхронизировать UI).
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Лайк не найден",
        )

    await session.commit()
    return None
