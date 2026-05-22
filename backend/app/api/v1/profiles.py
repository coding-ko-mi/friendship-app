"""Profile router."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_session
from app.models.user import User
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
