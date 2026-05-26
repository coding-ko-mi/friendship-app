"""
Репозиторий компаний и голосования — слой доступа к БД (только запросы).

Отвечает за работу с четырьмя таблицами:
  • groups          — компании
  • group_members   — состав компаний
  • membership_requests — заявки на изменение состава (join/invite/merge)
  • votes           — голоса по заявкам

Бизнес-решения (порог 75%, что считать принятым, кого добавлять) — НЕ здесь,
а в сервисном слое (group_service.py). Репозиторий лишь выполняет запросы.
Зеркалит стиль matching_repository.py: flush (не commit) внутри — транзакцией
управляет сервис.
"""
from __future__ import annotations

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import RequestStatus, RequestType
from app.models.group import Group, GroupMember
from app.models.matching import Match
from app.models.membership import MembershipRequest, Vote
from app.models.user import User


class GroupRepository:
    """Запросы к БД для компаний, заявок и голосования."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------ #
    #  КОМПАНИИ                                                          #
    # ------------------------------------------------------------------ #
    async def create_group(self, *, name: str) -> Group:
        """Создать компанию (без участников). Участников добавляет сервис отдельно."""
        group = Group(name=name)
        self.session.add(group)
        await self.session.flush()  # получить id, не закрывая транзакцию
        return group

    async def get_group(self, group_id: int) -> Group | None:
        """Достать компанию по id (без подгрузки участников)."""
        return await self.session.get(Group, group_id)

    async def add_member(self, *, user_id: int, group_id: int) -> GroupMember:
        """Добавить участника в компанию. Дубль (тот же user+group) предотвращён PK."""
        member = GroupMember(user_id=user_id, group_id=group_id)
        self.session.add(member)
        await self.session.flush()
        return member

    async def is_member(self, *, user_id: int, group_id: int) -> bool:
        """Состоит ли пользователь в компании."""
        stmt = select(GroupMember.user_id).where(
            GroupMember.user_id == user_id, GroupMember.group_id == group_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_member_ids(self, group_id: int) -> list[int]:
        """ID всех участников компании (нужны для подсчёта голосов и порога)."""
        stmt = select(GroupMember.user_id).where(GroupMember.group_id == group_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_members(self, group_id: int) -> int:
        """Число участников компании (для проверки MAX_GROUP_SIZE и порога 75%)."""
        stmt = select(func.count(GroupMember.user_id)).where(
            GroupMember.group_id == group_id
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def list_groups_of_user(self, user_id: int) -> list[tuple[Group, int]]:
        """
        Все компании, в которых состоит пользователь, + размер каждой.

        Для экрана «Матчи → Компании»: достаточно лёгкого списка
        (id, name, member_count). Возвращаем пары (Group, member_count),
        чтобы избежать N+1 при подсчёте состава отдельным запросом.
        """
        # Подзапрос: количество участников по каждой компании.
        member_count_subq = (
            select(
                GroupMember.group_id.label("gid"),
                func.count(GroupMember.user_id).label("cnt"),
            )
            .group_by(GroupMember.group_id)
            .subquery()
        )

        stmt = (
            select(Group, func.coalesce(member_count_subq.c.cnt, 0))
            .join(GroupMember, GroupMember.group_id == Group.id)
            .outerjoin(member_count_subq, member_count_subq.c.gid == Group.id)
            .where(GroupMember.user_id == user_id)
            .order_by(Group.id.desc())
        )
        result = await self.session.execute(stmt)
        return [(row[0], int(row[1])) for row in result.all()]

    async def get_members(self, group_id: int) -> list[User]:
        """Участники компании как объекты User (для карточки состава)."""
        stmt = (
            select(User)
            .join(GroupMember, GroupMember.user_id == User.id)
            .where(GroupMember.group_id == group_id)
            .order_by(User.id.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_member_cities(self, group_id: int) -> list[str]:
        """
        Города всех участников компании (для достижения «Без границ»).

        Возвращаем именно список (с дублями), а не множество: сервису удобно
        просто посчитать `len(set(...))`, а одинокое первое сравнение «> 1»
        работает в обоих случаях. Запрос быстрее, чем подгружать User целиком,
        потому что выбираем одно поле.
        """
        stmt = (
            select(User.city)
            .join(GroupMember, GroupMember.user_id == User.id)
            .where(GroupMember.group_id == group_id)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_group(self, group_id: int) -> None:
        """
        Удалить компанию. Используется при merge: присоединяемая (subject)
        компания удаляется после переезда участников. CASCADE снимает её
        членства и заявки автоматически (см. ondelete='CASCADE' в схеме).
        """
        await self.session.execute(delete(Group).where(Group.id == group_id))

    # ------------------------------------------------------------------ #
    #  МЭТЧИ (для создания компании из мэтча — Вариант 2)               #
    # ------------------------------------------------------------------ #
    async def get_match(self, match_id: int) -> Match | None:
        """Достать мэтч по id (проверка, что компания рождается из реального мэтча)."""
        return await self.session.get(Match, match_id)

    # ------------------------------------------------------------------ #
    #  ЗАЯВКИ                                                            #
    # ------------------------------------------------------------------ #
    async def create_request(
        self,
        *,
        type_: RequestType,
        target_group_id: int,
        subject_user_id: int | None = None,
        subject_group_id: int | None = None,
    ) -> MembershipRequest:
        """
        Создать заявку. Статус сразу VOTING (на MVP отдельной стадии PENDING нет).
        Ровно один субъект (user XOR group) — гарантия на стороне сервиса и CHECK БД.
        """
        request = MembershipRequest(
            type=type_,
            status=RequestStatus.VOTING,
            target_group_id=target_group_id,
            subject_user_id=subject_user_id,
            subject_group_id=subject_group_id,
        )
        self.session.add(request)
        await self.session.flush()
        return request

    async def get_request(self, request_id: int) -> MembershipRequest | None:
        """Достать заявку по id."""
        return await self.session.get(MembershipRequest, request_id)

    async def get_requests_for_group(
        self, group_id: int, *, only_active: bool = True
    ) -> list[MembershipRequest]:
        """
        Заявки, по которым голосует данная компания (target_group_id == group_id).

        only_active=True — только идущие голосования (status=VOTING); это то, что
        участникам компании надо видеть и по чему голосовать.
        """
        stmt = select(MembershipRequest).where(
            or_(
                MembershipRequest.target_group_id == group_id,
                MembershipRequest.subject_group_id == group_id,
            )
        )
        if only_active:
            stmt = stmt.where(MembershipRequest.status == RequestStatus.VOTING)
        stmt = stmt.order_by(MembershipRequest.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def set_request_status(
        self, request: MembershipRequest, status: RequestStatus
    ) -> None:
        """Сменить статус заявки (VOTING → ACCEPTED / REJECTED). Commit — на сервисе."""
        request.status = status
        self.session.add(request)
        await self.session.flush()

    async def has_pending_join(
        self, *, subject_user_id: int, target_group_id: int
    ) -> bool:
        """
        Есть ли уже активная (VOTING) заявка этого одиночки в эту же компанию.

        Защита от дублей: пока идёт голосование по join/invite того же человека
        в ту же компанию — повторную заявку не создаём.
        """
        stmt = select(MembershipRequest.id).where(
            MembershipRequest.subject_user_id == subject_user_id,
            MembershipRequest.target_group_id == target_group_id,
            MembershipRequest.status == RequestStatus.VOTING,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    # ------------------------------------------------------------------ #
    #  ГОЛОСА                                                            #
    # ------------------------------------------------------------------ #
    async def vote_exists(self, *, request_id: int, voter_id: int) -> bool:
        """Голосовал ли уже этот участник по этой заявке (запрет двойного голоса)."""
        stmt = select(Vote.id).where(
            Vote.request_id == request_id, Vote.voter_id == voter_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def add_vote(
        self, *, request_id: int, voter_id: int, value: bool
    ) -> Vote:
        """Записать голос. UniqueConstraint в схеме страхует от дублей на уровне БД."""
        vote = Vote(request_id=request_id, voter_id=voter_id, value=value)
        self.session.add(vote)
        await self.session.flush()
        return vote

    async def count_votes(
        self, *, request_id: int, voter_ids: list[int]
    ) -> tuple[int, int]:
        """
        Посчитать голоса «за»/«против» по заявке СРЕДИ заданных голосующих.

        voter_ids — состав конкретной компании. Для merge это важно: голоса всех
        участников обеих компаний лежат под одним request_id, но порог считается
        по каждой компании отдельно — поэтому считаем только голоса «своих».

        Возвращает (votes_yes, votes_no).
        """
        if not voter_ids:
            return 0, 0

        stmt = (
            select(Vote.value, func.count(Vote.id))
            .where(
                Vote.request_id == request_id,
                Vote.voter_id.in_(voter_ids),
            )
            .group_by(Vote.value)
        )
        result = await self.session.execute(stmt)
        yes = no = 0
        for value, cnt in result.all():
            if value:
                yes = int(cnt)
            else:
                no = int(cnt)
        return yes, no
