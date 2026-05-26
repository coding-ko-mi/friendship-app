"""
Репозиторий мэтчинга — слой доступа к БД (только запросы, без бизнес-логики).

Отвечает за три вещи:
  1. Достать кандидатов для ленты с фильтрами и подсчётом общих интересов.
  2. Работа с лайками (создать, проверить встречный).
  3. Работа с мэтчами (создать в каноническом порядке, проверить существование).

Бизнес-решения (что считать мэтчем, какой порог, какой TTL) — НЕ здесь,
а в сервисном слое. Репозиторий лишь выполняет запросы, которые ему велят.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interest import user_interests
from app.models.matching import Like, Match
from app.models.user import User


class MatchingRepository:
    """Запросы к БД для подбора и мэтчинга одиночек."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------ #
    #  ЛЕНТА КАНДИДАТОВ                                                   #
    # ------------------------------------------------------------------ #
    async def fetch_candidates(
        self,
        *,
        current_user_id: int,
        current_user_interest_ids: list[int],
        city: str,
        age_min: int,
        age_max: int,
        excluded_ids: list[int],
        cursor: int | None,
        limit: int,
    ) -> list[tuple[User, int]]:
        """
        Вернуть кандидатов для ленты, отсортированных по числу общих интересов.

        Возвращает список пар (User, сколько_общих_интересов).

        Фильтры (жёсткие — кого вообще показываем):
          • тот же город (гео-близость на MVP = точное совпадение city);
          • возраст в диапазоне [age_min, age_max] (диапазон задаёт анкета);
          • не сам пользователь;
          • не забаненные;
          • не из excluded_ids (уже лайкнутые + временно скипнутые).

        Сортировка (мягкая — в каком порядке):
          • больше общих интересов → выше. Это и есть «скоринг» по продукту:
            интересы решают порядок, фильтры решают состав.

        Пагинация — по курсору (id последнего кандидата), а не OFFSET:
          стабильнее при подгрузке и дешевле для БД.
        """
        # Подзапрос: для каждого кандидата считаем, со сколькими интересами
        # текущего пользователя он пересекается. Если у текущего интересов нет,
        # пересечение = 0 у всех (лента просто не ранжируется по интересам).
        shared_count = func.count(user_interests.c.interest_id).label("shared_count")

        stmt = (
            select(User, shared_count)
            # LEFT JOIN на связку интересов кандидата, но считаем только те строки,
            # где interest_id входит в интересы текущего пользователя.
            .outerjoin(
                user_interests,
                and_(
                    user_interests.c.user_id == User.id,
                    user_interests.c.interest_id.in_(current_user_interest_ids)
                    if current_user_interest_ids
                    # Пустой список интересов: условие, которое всегда ложно,
                    # чтобы JOIN не дал совпадений (иначе in_([]) ведёт себя странно).
                    else False,
                ),
            )
            .where(
                User.id != current_user_id,       # не показываем самого себя
                User.is_banned.is_(False),         # забаненных не показываем
                User.city == city,                 # тот же город
                User.age >= age_min,               # нижняя граница возраста
                User.age <= age_max,               # верхняя граница возраста
            )
            .group_by(User.id)
            # Сортировка: сперва по числу общих интересов (по убыванию),
            # затем по id (по возрастанию) — стабильный детерминированный порядок.
            .order_by(shared_count.desc(), User.id.asc())
            .limit(limit)
        )

        # Исключаем уже показанных/лайкнутых (если список не пуст).
        if excluded_ids:
            stmt = stmt.where(User.id.notin_(excluded_ids))

        # Курсорная пагинация: берём кандидатов с id больше курсора.
        # Работает вместе с тем, что вторичная сортировка идёт по User.id.
        if cursor is not None:
            stmt = stmt.where(User.id > cursor)

        result = await self.session.execute(stmt)
        # result.all() вернёт строки вида (User, shared_count) — распаковываем в пары.
        return [(row[0], row[1]) for row in result.all()]

    async def get_shared_interest_names(
        self, *, current_user_interest_ids: list[int], candidate_id: int
    ) -> list[str]:
        """
        Названия интересов, общих между текущим пользователем и кандидатом.

        Нужно для карточки («что вас объединяет»). Вынесено отдельным запросом,
        чтобы не усложнять основной запрос ленты JOIN-ами с таблицей интересов.
        """
        if not current_user_interest_ids:
            return []

        from app.models.interest import Interest  # локальный импорт: только здесь нужен

        stmt = (
            select(Interest.name)
            .join(user_interests, user_interests.c.interest_id == Interest.id)
            .where(
                user_interests.c.user_id == candidate_id,
                Interest.id.in_(current_user_interest_ids),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_user_interest_ids(self, user_id: int) -> list[int]:
        """ID всех интересов пользователя. Нужны и для скоринга, и для карточек."""
        stmt = select(user_interests.c.interest_id).where(
            user_interests.c.user_id == user_id
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ------------------------------------------------------------------ #
    #  ЛАЙКИ                                                              #
    # ------------------------------------------------------------------ #
    async def get_liked_user_ids(self, user_id: int) -> list[int]:
        """ID всех, кого пользователь уже лайкнул (чтобы не показывать повторно)."""
        stmt = select(Like.to_user_id).where(Like.from_user_id == user_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def like_exists(self, *, from_user_id: int, to_user_id: int) -> bool:
        """Есть ли уже лайк from_user → to_user (защита от повторного лайка)."""
        stmt = select(Like.id).where(
            Like.from_user_id == from_user_id, Like.to_user_id == to_user_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def add_like(self, *, from_user_id: int, to_user_id: int) -> Like:
        """Создать лайк. Коммит делает сервис (он управляет транзакцией)."""
        like = Like(from_user_id=from_user_id, to_user_id=to_user_id)
        self.session.add(like)
        await self.session.flush()  # flush — получить id, но не завершить транзакцию
        return like

    # ------------------------------------------------------------------ #
    #  МЭТЧИ                                                              #
    # ------------------------------------------------------------------ #
    async def match_exists(self, *, user_a_id: int, user_b_id: int) -> Match | None:
        """
        Найти мэтч по канонической паре (a < b). Сервис обязан передать id
        уже упорядоченными — здесь не сортируем, чтобы не прятать ошибку вызова.
        """
        stmt = select(Match).where(
            Match.user_a_id == user_a_id, Match.user_b_id == user_b_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_match(self, *, user_a_id: int, user_b_id: int) -> Match:
        """
        Создать мэтч. Ожидает канонический порядок (user_a_id < user_b_id) —
        этого требует CHECK-ограничение схемы. Упорядочивание — на сервисе.
        """
        match = Match(user_a_id=user_a_id, user_b_id=user_b_id)
        self.session.add(match)
        await self.session.flush()
        return match

    async def get_target_user(self, user_id: int) -> User | None:
        """Достать пользователя по id (проверка существования цели лайка)."""
        return await self.session.get(User, user_id)

    # ------------------------------------------------------------------ #
    #  СПИСОК МЭТЧЕЙ (экран «Матчи»)                                     #
    # ------------------------------------------------------------------ #
    async def list_user_matches(
        self, user_id: int
    ) -> list[tuple[Match, User]]:
        """
        Все мэтчи пользователя + второй участник пары.

        Возвращает список пар (Match, other_user), отсортированных по дате
        создания (свежие сверху). Забаненные собеседники отфильтровываются.

        Запрос: JOIN matches с users — берём ту строку users, которая НЕ есть
        текущий пользователь (через CASE в JOIN-условии).
        """
        # Выбираем второго участника одним запросом: для каждой строки matches
        # подгружаем User, чей id = противоположной стороне пары.
        other_user = User  # alias для читаемости
        stmt = (
            select(Match, other_user)
            .join(
                other_user,
                or_(
                    and_(Match.user_a_id == user_id, other_user.id == Match.user_b_id),
                    and_(Match.user_b_id == user_id, other_user.id == Match.user_a_id),
                ),
            )
            .where(
                or_(Match.user_a_id == user_id, Match.user_b_id == user_id),
                other_user.is_banned.is_(False),
            )
            .order_by(Match.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    # ------------------------------------------------------------------ #
    #  ИСТОРИЯ ЛАЙКОВ (экран «История»)                                  #
    # ------------------------------------------------------------------ #
    async def list_likes_from(
        self, user_id: int
    ) -> list[tuple[User, datetime]]:
        """
        Список людей, которых пользователь лайкнул, + когда поставил лайк.

        Сортировка: свежие сверху. Забаненных целей не показываем — их
        UI всё равно ничего полезного не даст.
        """
        stmt = (
            select(User, Like.created_at)
            .join(Like, Like.to_user_id == User.id)
            .where(Like.from_user_id == user_id, User.is_banned.is_(False))
            .order_by(Like.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def delete_like(self, *, from_user_id: int, to_user_id: int) -> int:
        """
        Удалить лайк (используется на экране «История» — «убрать лайк»).

        Возвращает число удалённых строк (0 — лайка не было).
        Мэтч, если он есть с этим пользователем, НЕ удаляем — это отдельная
        логика, продуктово не сводится к «отозвал лайк».
        """
        stmt = delete(Like).where(
            Like.from_user_id == from_user_id, Like.to_user_id == to_user_id
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        # rowcount у delete возвращает число удалённых строк.
        return int(result.rowcount or 0)
