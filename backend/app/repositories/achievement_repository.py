"""
Репозиторий достижений — слой доступа к БД (только запросы).

Работает с двумя таблицами:
  • achievements        — справочник (код, имя, описание); наполняется seed-ом
  • user_achievements    — факты «пользователь получил достижение» (PK = user_id+achievement_id)

Бизнес-решения (когда выдавать, кому, слать ли пуш) — НЕ здесь, а в сервисе
(achievement_service.py). Репозиторий лишь выполняет запросы.

Стиль зеркалит group_repository / matching_repository: внутри только flush
(не commit) — транзакцией владеет вызывающий сервис. Это критично: выдача
FOUNDER должна попасть в ТОТ ЖЕ commit, что и создание компании, иначе
получится компания без достижения. Поэтому репозиторий не коммитит сам.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.achievement import Achievement, UserAchievement


class AchievementRepository:
    """Запросы к БД для справочника достижений и фактов их выдачи."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------ #
    #  СПРАВОЧНИК                                                        #
    # ------------------------------------------------------------------ #
    async def get_id_by_code(self, code: str) -> int | None:
        """
        id достижения по его коду (FOUNDER, FULL_HOUSE...).

        Возвращает None, если кода нет в справочнике — это сигнал, что seed
        не прогнан. Сервис трактует это как «нечего выдавать» (а не падает),
        чтобы отсутствие seed не ломало создание компании/мэтча.
        """
        stmt = select(Achievement.id).where(Achievement.code == code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Achievement]:
        """Весь справочник достижений (для витрины: показать карту прогресса)."""
        stmt = select(Achievement).order_by(Achievement.id.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ------------------------------------------------------------------ #
    #  ФАКТЫ ВЫДАЧИ                                                      #
    # ------------------------------------------------------------------ #
    async def has(self, *, user_id: int, achievement_id: int) -> bool:
        """Есть ли уже у пользователя это достижение (проверка перед выдачей)."""
        stmt = select(UserAchievement.user_id).where(
            UserAchievement.user_id == user_id,
            UserAchievement.achievement_id == achievement_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def add(self, *, user_id: int, achievement_id: int) -> None:
        """
        Записать факт выдачи достижения. Дубль защищён первичным ключом
        (user_id+achievement_id). Проверку «уже есть» делает сервис ДО вызова —
        здесь просто вставка с flush (id не нужен, нужна фиксация в транзакции).
        """
        link = UserAchievement(user_id=user_id, achievement_id=achievement_id)
        self.session.add(link)
        await self.session.flush()

    async def list_earned_ids(self, user_id: int) -> set[int]:
        """
        ID достижений, которые пользователь уже получил.

        Множество — чтобы витрина за один проход проставила флаг earned всему
        справочнику (achievement_id in earned_ids), без запроса на каждое.
        """
        stmt = select(UserAchievement.achievement_id).where(
            UserAchievement.user_id == user_id
        )
        result = await self.session.execute(stmt)
        return set(result.scalars().all())

    async def list_earned(self, user_id: int) -> list[UserAchievement]:
        """
        Полученные достижения пользователя С временем получения (earned_at).

        Нужно витрине, чтобы показать дату рядом с полученным достижением.
        Подгружаем сразу связанный Achievement (selectinload не нужен — берём
        отдельным проходом в сервисе по earned_ids; здесь отдаём «как есть»).
        """
        stmt = select(UserAchievement).where(UserAchievement.user_id == user_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
