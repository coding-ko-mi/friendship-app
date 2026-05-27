"""Profile router."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_session
from app.models.user import User
from app.redis_client import get_redis
from app.schemas.profile import ProfileOwnResponse, ProfilePublicResponse, ProfileUpdateRequest
from app.services.profile_service import ProfileNotFoundError, ProfileService

router = APIRouter(tags=["profiles"])


def _get_service(db: AsyncSession = Depends(get_session)) -> ProfileService:
    return ProfileService(db)


@router.get("/me/profile", response_model=ProfileOwnResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(_get_service),
) -> ProfileOwnResponse:
    """Получить свой профиль (полные данные)."""
    return await service.get_own_profile(current_user)


@router.patch("/me/profile", response_model=ProfileOwnResponse)
async def update_my_profile(
    body: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(_get_service),
) -> ProfileOwnResponse:
    """
    Обновить профиль. Передавай только изменяемые поля.

    Поля name, age, about, city меняются через Telegram-бота, не здесь.
    """
    return await service.update_own_profile(current_user, body)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_account(
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(_get_service),
    redis: Redis = Depends(get_redis),
) -> Response:
    """
    Полное удаление своего аккаунта.

    Удаляет пользователя из БД (CASCADE снимет все связанные данные:
    лайки, мэтчи, голоса, членства, заявки, достижения, интересы, профиль,
    анкету). Компании, где он был единственным участником, удаляются вместе
    с ним. Эфемерные данные пользователя в Redis (skip-набор, счётчики
    достижений) тоже очищаются. Действие необратимо.
    """
    await service.delete_account(current_user, redis)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/users/{user_id}/profile", response_model=ProfilePublicResponse)
async def get_user_profile(
    user_id: int,
    _: User = Depends(get_current_user),
    service: ProfileService = Depends(_get_service),
) -> ProfilePublicResponse:
    """Публичная карточка другого пользователя."""
    try:
        return await service.get_public_profile(user_id)
    except ProfileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
