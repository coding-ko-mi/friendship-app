"""
ProfileService — работа с профилями.

Объединяет данные из двух источников:
- User (существующая таблица): name, age, about, photo_file_id, city
- Profile (новая таблица): display_name, gender, geo, extra_photos, is_visible

Разделение намеренное: User-поля заполняются через Telegram-бот (aiogram FSM),
Profile-поля — через Mini App (FastAPI).
"""

from redis.asyncio import Redis
from sqlalchemy import delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.group import Group, GroupMember
from app.models.interest import Interest, user_interests
from app.models.profile import Profile
from app.models.user import User
from app.repositories.achievement_repository import AchievementRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.user_repository import UserRepository
from app.schemas.profile import (
    ProfileInterest,
    ProfileOwnResponse,
    ProfilePublicResponse,
    ProfileUpdateRequest,
)
from app.services.achievement_service import AchievementService


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
        interests = await self._load_user_interests(current_user.id)
        return self._build_own(profile, current_user, interests)

    async def update_own_profile(
        self, current_user: User, data: ProfileUpdateRequest
    ) -> ProfileOwnResponse:
        """
        PATCH профиля: обновляем только переданные поля.

        Profile-поля (display_name, gender, geo, is_visible, extra_photos) —
        исторически правились здесь. User-поля about и interest_ids добавлены
        для экрана «Профиль» Mini App: их редактирование живёт здесь же,
        чтобы фронт делал один PATCH вместо двух.
        """
        profile = await self._get_or_create_profile(current_user.id)

        update_data: dict = {}
        if data.display_name is not None:
            update_data["display_name"] = data.display_name
        if data.gender is not None:
            update_data["gender"] = data.gender.value
        if data.latitude is not None and data.longitude is not None:
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

        # --- User-поля (about, интересы) ---
        # about: пишем прямо в User; пустую строку валидатор схемы уже
        # превратил в None (т.е. «не менять»).
        if data.about is not None:
            current_user.about = data.about
            self.db.add(current_user)
            await self.db.flush()

        # Интересы: полная замена набора через ассоциативную таблицу.
        # None → не трогаем; [] или [ids...] → заменяем все.
        if data.interest_ids is not None:
            await self._replace_user_interests(current_user.id, data.interest_ids)

        await self.db.commit()
        await self.db.refresh(profile)
        await self.db.refresh(current_user)

        interests = await self._load_user_interests(current_user.id)
        return self._build_own(profile, current_user, interests)

    async def get_public_profile(self, user_id: int) -> ProfilePublicResponse:
        """Публичная карточка для показа другим пользователям."""
        user = await self.user_repo.get_by_id(user_id)
        if user is None or user.is_banned:
            raise ProfileNotFoundError("Пользователь не найден")

        profile = await self.profile_repo.get_by_user_id(user_id)
        if profile is None:
            profile = Profile(user_id=user_id)  # виртуальный, без сохранения

        # Заработанные достижения — собираем через тот же сервис, чтобы
        # логика «что показывать» жила в одном месте.
        achievement_service = AchievementService(
            achievement_repo=AchievementRepository(self.db)
        )
        achievements = await achievement_service.list_earned_public(user_id)

        return self._build_public(profile, user, achievements)

    async def create_for_user(self, user_id: int) -> Profile:
        """Вызывается при первом входе через Mini App."""
        return await self.profile_repo.create(user_id)

    async def delete_account(self, user: User, redis: Redis) -> None:
        """
        Полное удаление аккаунта пользователя.

        Что происходит:
          1. Находим компании, в которых пользователь — единственный участник,
             и удаляем их (после CASCADE-удаления group_members компания
             осталась бы «вырожденной» с 0 участников — это мусор).
          2. Удаляем User. CASCADE снимает: profiles, questionnaires,
             user_interests, user_achievements, likes, matches, group_members,
             membership_requests (как subject_user), votes.
          3. Чистим эфемерные данные пользователя в Redis: skip-набор и
             счётчики достижений. Скипы, в которых ЭТОТ user_id фигурирует
             у других пользователей, не трогаем — они истекут сами по TTL,
             а лента просто не покажет несуществующего человека.
        """
        # 1. Компании, где он единственный участник. Подзапрос: для каждой
        # группы пользователя считаем общее число её участников.
        member_count_subq = (
            select(
                GroupMember.group_id.label("gid"),
                func.count(GroupMember.user_id).label("cnt"),
            )
            .group_by(GroupMember.group_id)
            .subquery()
        )
        solo_groups_stmt = (
            select(GroupMember.group_id)
            .join(
                member_count_subq, member_count_subq.c.gid == GroupMember.group_id
            )
            .where(
                GroupMember.user_id == user.id,
                member_count_subq.c.cnt == 1,
            )
        )
        solo_group_ids = list(
            (await self.db.execute(solo_groups_stmt)).scalars().all()
        )
        if solo_group_ids:
            await self.db.execute(
                delete(Group).where(Group.id.in_(solo_group_ids))
            )

        # 2. Удаляем самого пользователя. Остальные связи снимет CASCADE.
        await self.db.execute(delete(User).where(User.id == user.id))
        await self.db.commit()

        # 3. Чистим эфемерное состояние в Redis. Делаем после commit:
        # если БД упадёт — Redis-данные не теряем зря.
        for key in (
            f"skip:{user.id}",
            f"ach:likes_given:{user.id}",
            f"ach:likes_received:{user.id}",
            f"ach:consecutive_skips:{user.id}",
            f"ach:votes_cast:{user.id}",
        ):
            await redis.delete(key)

    # ------------------------------------------------------------------

    async def _load_user_interests(self, user_id: int) -> list[ProfileInterest]:
        """
        Достать интересы пользователя как (id, name).

        Идём через ассоциативную таблицу user_interests → interests. Так не
        тащим всю модель Interest целиком и не зависим от eager-загрузки
        relationship на User.
        """
        stmt = (
            select(Interest.id, Interest.name)
            .join(user_interests, user_interests.c.interest_id == Interest.id)
            .where(user_interests.c.user_id == user_id)
            .order_by(Interest.id)
        )
        result = await self.db.execute(stmt)
        return [ProfileInterest(id=row[0], name=row[1]) for row in result.all()]

    async def _replace_user_interests(
        self, user_id: int, new_interest_ids: list[int]
    ) -> None:
        """
        Полная замена набора интересов пользователя.

        Стратегия «delete + insert» по ассоциативной таблице: проще, чем
        diff-логика, и операция редкая (раз в сессию редактирования).
        Дубли id-шников в new_interest_ids убираем set(), несуществующие
        id отфильтрует FK-ошибка при insert.
        """
        # Удаляем старые связи.
        await self.db.execute(
            delete(user_interests).where(user_interests.c.user_id == user_id)
        )
        # Вставляем новые (если есть что вставлять).
        unique_ids = list({i for i in new_interest_ids})
        if unique_ids:
            await self.db.execute(
                insert(user_interests),
                [{"user_id": user_id, "interest_id": iid} for iid in unique_ids],
            )
        await self.db.flush()

    async def _get_or_create_profile(self, user_id: int) -> Profile:
        profile = await self.profile_repo.get_by_user_id(user_id)
        if profile is None:
            profile = await self.profile_repo.create(user_id)
            await self.db.commit()
        return profile

    def _build_own(
        self,
        profile: Profile,
        user: User,
        interests: list[ProfileInterest],
    ) -> ProfileOwnResponse:
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
            interests=interests,
        )

    def _build_public(
        self,
        profile: Profile,
        user: User,
        achievements: list | None = None,
    ) -> ProfilePublicResponse:
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
            achievements=achievements or [],
        )
