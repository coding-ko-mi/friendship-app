"""
Сервис компаний и голосования — бизнес-логика модуля (сценарий Б).

Здесь принимаются все продуктовые решения:
  • создание компании из мэтча (Вариант 2: основатель + мэтч-партнёр);
  • создание заявок join / invite / merge с валидацией субъекта;
  • приём голоса с защитой от двойного голосования;
  • подсчёт порога 75% (округление вверх) — для merge раздельно по двум компаниям;
  • применение результата: добавление участника / переезд участников при merge;
  • проверка MAX_GROUP_SIZE перед добавлением.

Транспорт (HTTP) и доступ к БД сюда не лезут — сервис оркеструет репозиторий
и возвращает готовые схемы. Уведомления (мэтч принят / отклонён / создан чат)
НЕ отправляются здесь — это задача модуля «Бот». Сервис лишь меняет состояние.

Достижения (модуль «Бэкенд: достижения») выдаются прямо в местах событий через
AchievementService на ТОЙ ЖЕ сессии — то есть в одной транзакции с изменением
состава (атомарно):
  • FOUNDER    — при создании компании (основателю);
  • FULL_HOUSE — когда состав достиг FULL_HOUSE_SIZE (всем участникам);
  • NO_BORDERS — когда в компании есть люди из 2+ городов (всем участникам).
Конструктор сервиса и роутер при этом не изменились: AchievementService
собирается лениво из текущей сессии (см. _achievement_service).
"""
from __future__ import annotations

import math

from redis.asyncio import Redis

from app.config import FULL_HOUSE_SIZE, MAX_GROUP_SIZE
from app.models.enums import AchievementCode, RequestStatus, RequestType
from app.models.user import User
from app.repositories.achievement_repository import AchievementRepository
from app.repositories.group_repository import GroupRepository
from app.schemas.groups import (
    GroupCard,
    GroupMemberCard,
    RequestCard,
    VoteProgress,
    VoteResult,
)
from app.services.achievement_service import AchievementService
from app.services.events import enqueue_event, vote_result_event


# --------------------------------------------------------------------- #
#  Доменные ошибки (роутер превратит их в HTTP-ответы)                  #
# --------------------------------------------------------------------- #
class GroupError(Exception):
    """Базовая ошибка домена компаний."""


class NotFoundError(GroupError):
    """Запрашиваемая сущность (компания / заявка / мэтч / пользователь) не найдена."""


class PermissionError_(GroupError):
    """Действие не разрешено текущему пользователю (например, не участник компании)."""


class ValidationError_(GroupError):
    """Некорректные данные заявки (нет субъекта, два субъекта, лишний размер и т.п.)."""


class ConflictError(GroupError):
    """Конфликт состояния: дубль заявки, повторный голос, уже в компании."""


class GroupService:
    """Жизненный цикл компании и голосование по изменению состава."""

    def __init__(self, *, group_repo: GroupRepository, redis: Redis) -> None:
        self.group_repo = group_repo
        self._redis = redis

    # ================================================================== #
    #  ВСПОМОГАТЕЛЬНОЕ                                                    #
    # ================================================================== #
    @staticmethod
    def _threshold(members_total: int) -> int:
        """
        Сколько голосов «за» нужно для прохождения порога 75%.

        Округление ВВЕРХ: ceil(0.75 * N). Для маленьких компаний это даёт
        единогласие (N=2→2, N=3→3) — намеренно: в крошечной группе голос
        каждого должен иметь вес. N=4→3, N=8→6, N=20→15.
        """
        return math.ceil(0.75 * members_total)

    def _achievement_service(self) -> AchievementService:
        """
        Собрать сервис достижений на ТЕКУЩЕЙ сессии.

        Тот же session, что и у group_repo → выдача идёт в одной транзакции с
        изменением состава (коммит делает вызывающий метод). Конструктор
        GroupService и роутер при этом не меняются — сервис строится лениво.
        """
        return AchievementService(
            repo=AchievementRepository(self.group_repo.session)
        )

    async def _grant_founder_achievement(self, user_id: int) -> None:
        """
        Выдать достижение «Основатель» (FOUNDER) при создании компании.

        Идемпотентно и без commit: выдача в той же транзакции, что и создание
        компании. Если справочник не засижен — AchievementService тихо пропустит
        выдачу, и компания всё равно создастся (достижения не критичный путь).
        """
        await self._achievement_service().grant(
            user_id=user_id, code=AchievementCode.FOUNDER
        )

    async def _notify_vote_result(self, request, accepted: bool) -> None:
        """
        Поставить событие пуша в очередь после завершения голосования.

        Только для join/invite (есть конкретный заявитель). Merge пропускаем:
        у слияния нет единственного адресата — это решение двух компаний.
        Вызывается ПОСЛЕ коммита.
        """
        if request.type is RequestType.MERGE or request.subject_user_id is None:
            return
        group = await self.group_repo.get_group(request.target_group_id)
        if group is None:
            return
        await enqueue_event(
            self._redis,
            vote_result_event(
                user_id=request.subject_user_id,
                group_name=group.name,
                accepted=accepted,
            ),
        )

    async def _check_group_achievements(self, group_id: int) -> None:
        """
        Проверить и выдать достижения, зависящие от состава компании.

        Вызывается после ЛЮБОГО изменения состава (создание компании, приём
        заявки join/invite, merge):
          • FULL_HOUSE — состав достиг FULL_HOUSE_SIZE → всем участникам;
          • NO_BORDERS — в составе есть люди из 2+ городов → всем участникам.

        Идемпотентно: повторные вызовы (например, состав снова стал «полным»
        после merge) не выдают достижение дважды — об этом заботится grant.
        """
        members = await self.group_repo.get_members(group_id)
        member_ids = [m.id for m in members]
        service = self._achievement_service()

        # FULL_HOUSE: собран полный состав — «прохождение игры».
        if len(members) >= FULL_HOUSE_SIZE:
            await service.grant_many(
                user_ids=member_ids, code=AchievementCode.FULL_HOUSE
            )

        # NO_BORDERS: в компании представлены минимум два города.
        distinct_cities = {m.city for m in members}
        if len(distinct_cities) >= 2:
            await service.grant_many(
                user_ids=member_ids, code=AchievementCode.NO_BORDERS
            )

    # ================================================================== #
    #  СОЗДАНИЕ КОМПАНИИ (Вариант 2: из подтверждённого мэтча)          #
    # ================================================================== #
    async def create_group(
        self, *, founder: User, name: str, match_id: int
    ) -> GroupCard:
        """
        Создать компанию из подтверждённого мэтча.

        Правила:
          • мэтч должен существовать;
          • текущий пользователь (founder) должен быть его участником;
          • компания рождается сразу из ДВУХ человек — основателя и мэтч-партнёра;
          • основателю выдаётся FOUNDER, составу — достижения состава.

        Так голосование осмысленно с первого дня: следующая join-заявка считает
        порог от 2 участников (нужны оба «за»), а не от вырожденной «компании из 1».
        """
        match = await self.group_repo.get_match(match_id)
        if match is None:
            raise NotFoundError("Мэтч не найден")

        # founder обязан быть одной из сторон мэтча — иначе нельзя создавать
        # компанию «из чужого знакомства».
        if founder.id not in (match.user_a_id, match.user_b_id):
            raise PermissionError_("Вы не участник этого мэтча")

        # Партнёр — вторая сторона мэтча.
        partner_id = (
            match.user_b_id if match.user_a_id == founder.id else match.user_a_id
        )

        # Создаём компанию и добавляем обоих участников.
        group = await self.group_repo.create_group(name=name)
        await self.group_repo.add_member(user_id=founder.id, group_id=group.id)
        await self.group_repo.add_member(user_id=partner_id, group_id=group.id)

        # Достижение основателю.
        await self._grant_founder_achievement(founder.id)
        # Достижения состава: NO_BORDERS возможен уже на двух разных городах.
        await self._check_group_achievements(group.id)

        await self.group_repo.session.commit()

        return await self.get_group_card(group.id)

    async def get_group_card(self, group_id: int) -> GroupCard:
        """Собрать карточку компании с составом."""
        group = await self.group_repo.get_group(group_id)
        if group is None:
            raise NotFoundError("Компания не найдена")

        members = await self.group_repo.get_members(group_id)
        return GroupCard(
            id=group.id,
            name=group.name,
            telegram_chat_id=group.telegram_chat_id,
            members=[GroupMemberCard.model_validate(m) for m in members],
            member_count=len(members),
        )

    # ================================================================== #
    #  СОЗДАНИЕ ЗАЯВКИ (join / invite / merge)                          #
    # ================================================================== #
    async def create_request(
        self,
        *,
        current_user: User,
        target_group_id: int,
        type_: RequestType,
        subject_user_id: int | None = None,
        subject_group_id: int | None = None,
    ) -> RequestCard:
        """
        Создать заявку на изменение состава. Логика валидации зависит от типа.

          join   — одиночка (subject_user) просится в target-компанию.
                   Подать может сам одиночка. Голосует target.
          invite — target-компания зовёт одиночку (subject_user).
                   Подать может участник target. Голосует target.
          merge  — subject-компания вливается в target-компанию.
                   Подать может участник одной из компаний. Голосуют ОБЕ.

        Во всех случаях заявка создаётся в статусе VOTING.
        """
        target = await self.group_repo.get_group(target_group_id)
        if target is None:
            raise NotFoundError("Целевая компания не найдена")

        if type_ in (RequestType.JOIN, RequestType.INVITE):
            return await self._create_user_request(
                current_user=current_user,
                target_group_id=target_group_id,
                type_=type_,
                subject_user_id=subject_user_id,
                subject_group_id=subject_group_id,
            )
        if type_ is RequestType.MERGE:
            return await self._create_merge_request(
                current_user=current_user,
                target_group_id=target_group_id,
                subject_user_id=subject_user_id,
                subject_group_id=subject_group_id,
            )
        raise ValidationError_("Неизвестный тип заявки")

    async def _create_user_request(
        self,
        *,
        current_user: User,
        target_group_id: int,
        type_: RequestType,
        subject_user_id: int | None,
        subject_group_id: int | None,
    ) -> RequestCard:
        """Общая логика join/invite: субъект — одиночка."""
        if subject_user_id is None or subject_group_id is not None:
            raise ValidationError_(
                "Для join/invite нужен subject_user_id (и только он)"
            )

        if type_ is RequestType.JOIN:
            if subject_user_id != current_user.id:
                raise PermissionError_("Заявку на вступление подаёт сам пользователь")
        else:  # INVITE
            if not await self.group_repo.is_member(
                user_id=current_user.id, group_id=target_group_id
            ):
                raise PermissionError_("Приглашать может только участник компании")

        if await self.group_repo.is_member(
            user_id=subject_user_id, group_id=target_group_id
        ):
            raise ConflictError("Пользователь уже состоит в этой компании")

        current_size = await self.group_repo.count_members(target_group_id)
        if current_size + 1 > MAX_GROUP_SIZE:
            raise ValidationError_(
                f"Компания достигла лимита участников ({MAX_GROUP_SIZE})"
            )

        if await self.group_repo.has_pending_join(
            subject_user_id=subject_user_id, target_group_id=target_group_id
        ):
            raise ConflictError("По этому пользователю уже идёт голосование")

        request = await self.group_repo.create_request(
            type_=type_,
            target_group_id=target_group_id,
            subject_user_id=subject_user_id,
        )
        await self.group_repo.session.commit()
        return await self.get_request_card(request.id)

    async def _create_merge_request(
        self,
        *,
        current_user: User,
        target_group_id: int,
        subject_user_id: int | None,
        subject_group_id: int | None,
    ) -> RequestCard:
        """
        Логика merge: субъект — присоединяемая компания.

        Голосуют ОБЕ компании раздельно (каждая по 75%) — продуктовое решение.
        Подать может участник любой из двух компаний.
        """
        if subject_group_id is None or subject_user_id is not None:
            raise ValidationError_("Для merge нужен subject_group_id (и только он)")
        if subject_group_id == target_group_id:
            raise ValidationError_("Нельзя слить компанию саму с собой")

        subject = await self.group_repo.get_group(subject_group_id)
        if subject is None:
            raise NotFoundError("Присоединяемая компания не найдена")

        in_target = await self.group_repo.is_member(
            user_id=current_user.id, group_id=target_group_id
        )
        in_subject = await self.group_repo.is_member(
            user_id=current_user.id, group_id=subject_group_id
        )
        if not (in_target or in_subject):
            raise PermissionError_("Слияние инициирует участник одной из компаний")

        size_target = await self.group_repo.count_members(target_group_id)
        size_subject = await self.group_repo.count_members(subject_group_id)
        if size_target + size_subject > MAX_GROUP_SIZE:
            raise ValidationError_(
                f"Суммарный размер компаний превышает лимит ({MAX_GROUP_SIZE})"
            )

        request = await self.group_repo.create_request(
            type_=RequestType.MERGE,
            target_group_id=target_group_id,
            subject_group_id=subject_group_id,
        )
        await self.group_repo.session.commit()
        return await self.get_request_card(request.id)

    # ================================================================== #
    #  ГОЛОСОВАНИЕ                                                        #
    # ================================================================== #
    async def vote(
        self, *, current_user: User, request_id: int, value: bool
    ) -> VoteResult:
        """
        Подать голос по заявке.

        Правила:
          • заявка существует и в статусе VOTING;
          • голосующий — участник компании, которая вправе голосовать по этой
            заявке (для merge — любой из двух составов);
          • повторный голос запрещён;
          • после голоса пересчитываем пороги и, если результат определён,
            применяем заявку (принять/отклонить).
        """
        request = await self.group_repo.get_request(request_id)
        if request is None:
            raise NotFoundError("Заявка не найдена")
        if request.status is not RequestStatus.VOTING:
            raise ConflictError("Голосование по заявке уже завершено")

        voting_group_ids = await self._voting_group_ids(request)

        voter_group_ids = [
            gid
            for gid in voting_group_ids
            if await self.group_repo.is_member(
                user_id=current_user.id, group_id=gid
            )
        ]
        if not voter_group_ids:
            raise PermissionError_("Вы не вправе голосовать по этой заявке")

        if await self.group_repo.vote_exists(
            request_id=request_id, voter_id=current_user.id
        ):
            raise ConflictError("Вы уже проголосовали по этой заявке")

        await self.group_repo.add_vote(
            request_id=request_id, voter_id=current_user.id, value=value
        )

        result = await self._evaluate_and_finalize(request)
        await self.group_repo.session.commit()

        # Уведомляем заявителя об итоге голосования (только после коммита).
        if result.finalized:
            await self._notify_vote_result(
                request, accepted=(result.status is RequestStatus.ACCEPTED)
            )

        return result

    async def _voting_group_ids(self, request) -> list[int]:
        """
        Какие компании голосуют по заявке.

          join/invite — только target-компания;
          merge       — обе (target и subject) голосуют раздельно.
        """
        if request.type is RequestType.MERGE:
            return [request.target_group_id, request.subject_group_id]
        return [request.target_group_id]

    async def _evaluate_and_finalize(self, request) -> VoteResult:
        """
        Оценить голосование и, если исход определён, применить заявку.

        Исход определён, когда:
          • порог «за» достигнут во ВСЕХ голосующих компаниях → ACCEPTED;
          • ИЛИ хотя бы в одной компании достичь порога уже НЕВОЗМОЖНО
            (даже если все непроголосовавшие скажут «за») → REJECTED.

        Пока ни то, ни другое — голосование продолжается (VOTING).
        """
        voting_group_ids = await self._voting_group_ids(request)

        all_passed = True
        any_impossible = False

        for gid in voting_group_ids:
            member_ids = await self.group_repo.get_member_ids(gid)
            members_total = len(member_ids)
            yes, no = await self.group_repo.count_votes(
                request_id=request.id, voter_ids=member_ids
            )
            threshold = self._threshold(members_total)

            if yes < threshold:
                all_passed = False
            remaining = members_total - yes - no
            if yes + remaining < threshold:
                any_impossible = True

        added_user_id: int | None = None

        if any_impossible:
            await self.group_repo.set_request_status(request, RequestStatus.REJECTED)
            return VoteResult(
                request_id=request.id,
                status=RequestStatus.REJECTED,
                finalized=True,
            )

        if all_passed:
            added_user_id = await self._apply_accepted(request)
            await self.group_repo.set_request_status(request, RequestStatus.ACCEPTED)
            # Состав изменился — проверяем достижения состава целевой компании.
            # Для merge выжившая компания — target (subject удаляется).
            await self._check_group_achievements(request.target_group_id)
            return VoteResult(
                request_id=request.id,
                status=RequestStatus.ACCEPTED,
                finalized=True,
                added_user_id=added_user_id,
            )

        return VoteResult(
            request_id=request.id,
            status=RequestStatus.VOTING,
            finalized=False,
        )

    async def _apply_accepted(self, request) -> int | None:
        """
        Применить принятую заявку — изменить состав компании.

          join/invite — добавить одиночку в target-компанию.
          merge       — переселить участников subject-компании в target,
                        затем удалить subject-компанию.

        Возвращает id добавленного одиночки (для join/invite) или None (merge).
        """
        if request.type in (RequestType.JOIN, RequestType.INVITE):
            await self.group_repo.add_member(
                user_id=request.subject_user_id,
                group_id=request.target_group_id,
            )
            return request.subject_user_id

        # MERGE: переносим участников subject → target, избегая дублей.
        subject_member_ids = await self.group_repo.get_member_ids(
            request.subject_group_id
        )
        target_member_ids = set(
            await self.group_repo.get_member_ids(request.target_group_id)
        )
        for uid in subject_member_ids:
            if uid not in target_member_ids:
                await self.group_repo.add_member(
                    user_id=uid, group_id=request.target_group_id
                )
        # Удаляем поглощённую компанию (CASCADE снимет её членства/заявки).
        await self.group_repo.delete_group(request.subject_group_id)
        return None

    # ================================================================== #
    #  ПРЕДСТАВЛЕНИЕ ЗАЯВКИ + ПРОГРЕСС ГОЛОСОВАНИЯ                       #
    # ================================================================== #
    async def get_request_card(self, request_id: int) -> RequestCard:
        """Карточка заявки + прогресс голосования по каждой голосующей компании."""
        request = await self.group_repo.get_request(request_id)
        if request is None:
            raise NotFoundError("Заявка не найдена")

        progress: list[VoteProgress] = []
        for gid in await self._voting_group_ids(request):
            member_ids = await self.group_repo.get_member_ids(gid)
            members_total = len(member_ids)
            yes, no = await self.group_repo.count_votes(
                request_id=request.id, voter_ids=member_ids
            )
            threshold = self._threshold(members_total)
            progress.append(
                VoteProgress(
                    group_id=gid,
                    members_total=members_total,
                    votes_yes=yes,
                    votes_no=no,
                    threshold=threshold,
                    passed=yes >= threshold,
                )
            )

        return RequestCard(
            id=request.id,
            type=request.type,
            status=request.status,
            subject_user_id=request.subject_user_id,
            subject_group_id=request.subject_group_id,
            target_group_id=request.target_group_id,
            created_at=request.created_at,
            progress=progress,
        )

    async def get_group_requests(self, group_id: int) -> list[RequestCard]:
        """Активные заявки, по которым голосует данная компания."""
        requests = await self.group_repo.get_requests_for_group(
            group_id, only_active=True
        )
        return [await self.get_request_card(r.id) for r in requests]
