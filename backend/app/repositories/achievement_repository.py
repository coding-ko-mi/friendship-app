"""
Репозиторий достижений — слой доступа к БД (только запросы).

Работает с двумя таблицами:
  • achievements        — справочник (что вообще существует);
  • user_achievements   — кто что получил (+ когда, earned_at).

Бизнес-решения («когда выдавать», «кому») — НЕ здесь, а в сервисе
(achievement_service.py) и в местах событий (создание компании, мэтч).
Репозиторий лишь выполняет запросы.

Транзакцией управляет вызывающий код: внутри — только flush (как в
group_repository / matching_repository). Это критично для выдачи: FOUNDER
вставляется внутри транзакции создания компании и коммитится вместе с ней.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.achievement import Achievement, UserAchievement


class AchievementRepository:
    """Запросы к БД для справочника достижений и выданных достижений."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------ #
    #  СПРАВОЧНИК                                                        #
    # ------------------------------------------------------------------ #
    async def get_by_code(self, code: str) -> Achievement | None:
        """
        Найти достижение в справочнике по коду (FOUNDER, FULL_HOUSE...).

        Возвращает None, если справочник не наполнен (seed не прогнан) или код
        отсутствует. Сервис трактует None как «выдавать нечего» и тихо выходит —
        ядро из-за ненаполненного справочника падать не должно.
        """
        stmt = select(Achievement).where(Achievement.code == code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Achievement]:
        """Весь справочник — для витрины (показать в т.ч. ещё не полученные)."""
        stmt = select(Achievement).order_by(Achievement.id.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ------------------------------------------------------------------ #
    #  ВЫДАННЫЕ ДОСТИЖЕНИЯ                                               #
    # ------------------------------------------------------------------ #
    async def has(self, *, user_id: int, achievement_id: int) -> bool:
        """
        Есть ли уже у пользователя это достижение.

        Защита от повторной выдачи на уровне приложения. На уровне БД повтор
        всё равно невозможен (PK = пара user_id + achievement_id), но проверка
        здесь даёт идемпотентность без ловли исключения о нарушении PK.
        """
        stmt = select(UserAchievement.user_id).where(
            UserAchievement.user_id == user_id,
            UserAchievement.achievement_id == achievement_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def add(self, *, user_id: int, achievement_id: int) -> UserAchievement:
        """
        Выдать достижение (вставить связь user ↔ achievement).

        flush, не commit: транзакцию закрывает вызывающий сервис. earned_at
        проставляется БД (server_default=now()).
        """
        link = UserAchievement(user_id=user_id, achievement_id=achievement_id)
        self.session.add(link)
        await self.session.flush()
        return link

    async def list_user(self, user_id: int) -> list[UserAchievement]:
        """
        Полученные пользователем достижения вместе с данными справочника.

        joinedload подтягивает Achievement одним запросом — на витрине нужны
        name/description/earned_at, без него был бы N+1.
        """
        stmt = (
            select(UserAchievement)
            .where(UserAchievement.user_id == user_id)
            .options(joinedload(UserAchievement.achievement))
            .order_by(UserAchievement.earned_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def earned_ids(self, user_id: int) -> set[int]:
        """
        Множество id достижений, которые у пользователя уже есть.

        Для витрины: пройти весь справочник и пометить, что получено, а что нет,
        одним проходом — без отдельного запроса на каждое достижение.
        """
        stmt = select(UserAchievement.achievement_id).where(
            UserAchievement.user_id == user_id
        )
        result = await self.session.execute(stmt)
        return set(result.scalars().all())
