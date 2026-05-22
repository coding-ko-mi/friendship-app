"""
ProfileService — работа с профилями.

Объединяет данные из двух источников:
- User (существующая таблица): name, age, about, photo_file_id, city
- Profile (новая таблица): display_name, gender, geo, extra_photos, is_visible

Разделение намеренное: User-поля заполняются через Telegram-бот (aiogram FSM),
Profile-поля — через Mini App (FastAPI).
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import Profile
from app.models.user import User
from app.repositories.profile_repository import ProfileRepository
from app.repositories.user_repository import UserRepository
from app.schemas.profile import (
    ProfileOwnResponse,
    ProfilePublicResponse,
    ProfileUpdateRequest,
)


class ProfileNotFoundError(Exception):
    pass


class ProfileService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.profile_repo = ProfileRepository(db)
        self.user_repo = UserRepository(db)

    async def get_own_profile(self, current_user: User) -> ProfileOwnResponse:
        """Получить полный профиль текущего пользователя."""
        profile = await self._get_or_create_profile(current_user.id)
        return self._build_own(profile, current_user)

    async def update_own_profile(
        self, current_user: User, data: ProfileUpdateRequest
    ) -> ProfileOwnResponse:
        """PATCH профиля: обновляем только переданные поля."""
        profile = await self._get_or_create_profile(current_user.id)

        update_data: dict = {}
        if data.display_name is not None:
            update_data["display_name"] = data.display_name
        if data.gender is not None:
            update_data["gender"] = data.gender.value
        if data.latitude is not None:
            update_data["latitude"] = data.latitude
            update_data["longitude"] = data.longitude
        if data.is_visible is not None:
            update_data["is_visible"] = data.is_visible

        # Фото — полная замена списка
        if data.extra_photos_urls is not None:
            profile.set_extra_photos(data.extra_photos_urls)
            await self.db.flush()

        if update_data:
            profile = await self.profile_repo.update(profile, update_data)

        await self.db.commit()
        await self.db.refresh(profile)
        return self._build_own(profile, current_user)

    async def get_public_profile(self, user_id: int) -> ProfilePublicResponse:
        """Публичная карточка для показа другим пользователям."""
        user = await self.user_repo.get_by_id(user_id)
        if user is None or user.is_banned:
            raise ProfileNotFoundError("Пользователь не найден")

        profile = await self.profile_repo.get_by_user_id(user_id)
        if profile is None:
            profile = Profile(user_id=user_id)  # виртуальный, без сохранения

        return self._build_public(profile, user)

    async def create_for_user(self, user_id: int) -> Profile:
        """Вызывается при первом входе через Mini App."""
        return await self.profile_repo.create(user_id)

    # ------------------------------------------------------------------

    async def _get_or_create_profile(self, user_id: int) -> Profile:
        profile = await self.profile_repo.get_by_user_id(user_id)
        if profile is None:
            profile = await self.profile_repo.create(user_id)
            await self.db.commit()
        return profile

    def _build_own(self, profile: Profile, user: User) -> ProfileOwnResponse:
        return ProfileOwnResponse(
            user_id=user.id,
            name=user.name,
            age=user.age,
            about=user.about,
            photo_file_id=user.photo_file_id,
            city=user.city,
            display_name=profile.display_name,
            gender=profile.gender,
            extra_photos=profile.get_extra_photos(),
            is_visible=profile.is_visible,
            latitude=float(profile.latitude) if profile.latitude else None,
            longitude=float(profile.longitude) if profile.longitude else None,
        )

    def _build_public(self, profile: Profile, user: User) -> ProfilePublicResponse:
        return ProfilePublicResponse(
            user_id=user.id,
            name=user.name,
            age=user.age,
            about=user.about,
            city=user.city,
            photo_file_id=user.photo_file_id,
            display_name=profile.display_name,
            gender=profile.gender,
            extra_photos=profile.get_extra_photos(),
        )
