"""
Сервис мэтчинга — бизнес-логика модуля (сценарий А: одиночка ↔ одиночка).

Здесь принимаются продуктовые решения:
  • как собрать ленту (фильтры + скоринг по интересам);
  • что происходит при лайке (создать лайк, проверить встречный → мэтч);
  • канонический порядок пары в Match (user_a_id < user_b_id);
  • как работает skip.

Транспорт (HTTP) и доступ к БД сюда не лезут — сервис оркеструет репозитории
и возвращает готовые схемы. При взаимном мэтче сервис: создаёт Match, выдаёт
обоим достижение FIRST_MEETING (в той же транзакции) и кладёт в events-очередь
пуши о мэтче и о достижении (ПОСЛЕ commit, по контракту events.py).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis

from app.config import (
    CHOOSY_THRESHOLD,
    DISCOVERY_PAGE_SIZE,
    FAST_FRIENDS_WINDOW_HOURS,
    OPEN_HEART_THRESHOLD,
    POPULAR_THRESHOLD,
)
from app.models.enums import AchievementCode
from app.models.user import User
from app.repositories.achievement_counters import AchievementCounters
from app.repositories.achievement_repository import AchievementRepository
from app.repositories.matching_repository import MatchingRepository
from app.repositories.skip_repository import SkipRepository
from app.schemas.matching import (
    CandidateCard,
    DiscoveryFeed,
    LikeResult,
    SkipResult,
)
from app.services.achievement_service import AchievementService
from app.services.events import achievement_event, enqueue_event, match_event


# Человекочитаемые имена достижений для пушей. Дублируем здесь, чтобы не лезть
# в БД ради текста на каждый пуш (его и так знает витрина / справочник). Если
# хочется централизованного источника — вынести в helper в achievement_service.
_NAME_OPEN_HEART = "Открытое сердце"
_NAME_POPULAR = "Популярный"
_NAME_CHOOSY = "Разборчивый"
_NAME_FAST_FRIENDS = "Быстрый старт"


class MatchingError(Exception):
    """Базовая ошибка домена мэтчинга (роутер превратит её в HTTP-ответ)."""


class SelfActionError(MatchingError):
    """Попытка лайкнуть/скипнуть самого себя."""


class TargetNotFoundError(MatchingError):
    """Цель действия (пользователь) не найдена или забанена."""


class MatchingService:
    """Подбор кандидатов и мэтчинг одиночек."""

    def __init__(
        self,
        *,
        matching_repo: MatchingRepository,
        skip_repo: SkipRepository,
        achievement_service: AchievementService,
        redis: Redis,
    ) -> None:
        self.matching_repo = matching_repo
        self.skip_repo = skip_repo
        # Для выдачи FIRST_MEETING обоим участникам нового мэтча.
        self.achievement_service = achievement_service
        # Для пушей (мэтч + достижение) в events-очередь после commit.
        self.redis = redis
        # Счётчики достижений (OPEN_HEART, POPULAR, CHOOSY) — в Redis.
        # Состоят из одних INCR/DEL, поэтому отдельная тонкая обёртка вместо
        # размазывания этих команд по бизнес-логике лайка/скипа.
        self.counters = AchievementCounters(redis)

    # ------------------------------------------------------------------ #
    #  ЛЕНТА                                                             #
    # ------------------------------------------------------------------ #
    async def get_feed(
        self,
        *,
        current_user: User,
        age_min: int,
        age_max: int,
        cursor: int | None = None,
        limit: int = DISCOVERY_PAGE_SIZE,
    ) -> DiscoveryFeed:
        """
        Собрать страницу ленты для текущего пользователя.

        Алгоритм:
          1. Берём интересы текущего пользователя (основа скоринга).
          2. Собираем список исключений: кого уже лайкнул + кого скипнул.
          3. Запрашиваем кандидатов из БД с фильтрами (город/возраст) и
             сортировкой по числу общих интересов.
          4. Для каждого достаём названия общих интересов (для карточки).
          5. Формируем курсор для следующей страницы.

        Возраст приходит из анкеты (partner_age_min/max) — диапазон считает
        вызывающий код (роутер/зависимость), сервис принимает уже готовые границы.
        """
        # 1. Интересы текущего пользователя — по ним считается совпадение.
        my_interest_ids = await self.matching_repo.get_user_interest_ids(
            current_user.id
        )

        # 2. Исключения: уже лайкнутые (из БД) + скипнутые (из Redis).
        liked_ids = await self.matching_repo.get_liked_user_ids(current_user.id)
        skipped_ids = await self.skip_repo.get_skipped_ids(current_user.id)
        # set убирает дубли, если кандидат и лайкнут, и скипнут.
        excluded_ids = list(set(liked_ids) | set(skipped_ids))

        # 3. Кандидаты с фильтрами и скорингом.
        rows = await self.matching_repo.fetch_candidates(
            current_user_id=current_user.id,
            current_user_interest_ids=my_interest_ids,
            city=current_user.city,
            age_min=age_min,
            age_max=age_max,
            excluded_ids=excluded_ids,
            cursor=cursor,
            limit=limit,
        )

        # 4. Собираем карточки. Для каждой подтягиваем общие интересы по названиям.
        candidates: list[CandidateCard] = []
        for candidate, shared_count in rows:
            shared_names = await self.matching_repo.get_shared_interest_names(
                current_user_interest_ids=my_interest_ids,
                candidate_id=candidate.id,
            )
            card = CandidateCard.model_validate(candidate)
            card.shared_interests = shared_names
            card.shared_count = shared_count
            candidates.append(card)

        # 5. Курсор следующей страницы = id последнего кандидата.
        # Если кандидатов меньше лимита — страниц больше нет (next_cursor=None).
        next_cursor = candidates[-1].id if len(candidates) == limit else None

        return DiscoveryFeed(candidates=candidates, next_cursor=next_cursor)

    # ------------------------------------------------------------------ #
    #  ЛАЙК                                                              #
    # ------------------------------------------------------------------ #
    async def like(self, *, from_user: User, to_user_id: int) -> LikeResult:
        """
        Поставить лайк и проверить взаимность.

        Логика:
          • нельзя лайкнуть себя;
          • цель должна существовать и не быть забаненной;
          • повторный лайк — не ошибка, просто возвращаем текущее состояние;
          • если встречный лайк уже есть → создаём Match (канонический порядок).

        Возвращает is_mutual (+ match_id, если мэтч). Пуш о мэтче — модуль «Бот».
        """
        # Защита: лайк самому себе. CHECK в БД это тоже ловит, но лучше отдать
        # понятную доменную ошибку до запроса в базу.
        if from_user.id == to_user_id:
            raise SelfActionError("Нельзя лайкнуть самого себя")

        # Цель существует и не забанена?
        target = await self.matching_repo.get_target_user(to_user_id)
        if target is None or target.is_banned:
            raise TargetNotFoundError("Пользователь не найден")

        # Повторный лайк — идемпотентно. Проверяем, не было ли уже мэтча,
        # чтобы вернуть консистентный ответ.
        already_liked = await self.matching_repo.like_exists(
            from_user_id=from_user.id, to_user_id=to_user_id
        )

        # Счётчики достижений (OPEN_HEART/POPULAR/CHOOSY) считаем ТОЛЬКО для
        # реально нового лайка — иначе при повторном тапе цифры дрейфовали бы.
        # Накопленные пуши-уведомления о новых достижениях отправим ПОСЛЕ
        # commit (контракт events.py).
        achievement_pushes: list[tuple[int, str]] = []  # (user_id, name)

        if not already_liked:
            await self.matching_repo.add_like(
                from_user_id=from_user.id, to_user_id=to_user_id
            )
            # Лайк прерывает серию скипов (CHOOSY — это «20 подряд БЕЗ лайка»).
            await self.counters.reset_consecutive_skips(from_user.id)

            # OPEN_HEART: лайкнул столько-то людей.
            given = await self.counters.incr_likes_given(from_user.id)
            if given == OPEN_HEART_THRESHOLD:
                if await self.achievement_service.grant(
                    user_id=from_user.id, code=AchievementCode.OPEN_HEART.value
                ):
                    achievement_pushes.append((from_user.id, _NAME_OPEN_HEART))

            # POPULAR: получатель лайка набрал столько-то входящих.
            received = await self.counters.incr_likes_received(to_user_id)
            if received == POPULAR_THRESHOLD:
                if await self.achievement_service.grant(
                    user_id=to_user_id, code=AchievementCode.POPULAR.value
                ):
                    achievement_pushes.append((to_user_id, _NAME_POPULAR))

        # Есть ли встречный лайк (target → from_user)? Если да — это мэтч.
        reciprocal = await self.matching_repo.like_exists(
            from_user_id=to_user_id, to_user_id=from_user.id
        )

        if not reciprocal:
            # Взаимности пока нет — лайк сохранён, ждём ответного шага.
            await self.matching_repo.session.commit()
            # Пуши о достижениях за лайк/получение лайка — после commit.
            for uid, name in achievement_pushes:
                await enqueue_event(
                    self.redis, achievement_event(user_id=uid, achievement_name=name)
                )
            return LikeResult(is_mutual=False)

        # --- Взаимный лайк: создаём (или находим) Match ---
        # Канонический порядок: меньший id всегда user_a. Этого требует
        # CHECK-ограничение ck_match_canonical_order и UniqueConstraint пары.
        user_a_id, user_b_id = sorted((from_user.id, to_user_id))

        existing = await self.matching_repo.match_exists(
            user_a_id=user_a_id, user_b_id=user_b_id
        )
        if existing is not None:
            # Мэтч уже был (например, гонка двойного лайка) — не дублируем.
            await self.matching_repo.session.commit()
            return LikeResult(is_mutual=True, match_id=existing.id)

        match = await self.matching_repo.add_match(
            user_a_id=user_a_id, user_b_id=user_b_id
        )

        # FIRST_MEETING обоим участникам нового мэтча — в ТУ ЖЕ транзакцию, что и
        # сам Match (атомарно: либо мэтч с достижениями, либо ничего). Запоминаем,
        # кому выдано впервые, чтобы после commit отправить пуш о достижении.
        first_meeting_granted = await self.achievement_service.grant_many(
            user_ids=[from_user.id, to_user_id],
            code=AchievementCode.FIRST_MEETING.value,
        )

        # FAST_FRIENDS — «первое знакомство в первые сутки после регистрации».
        # Условие: это первый мэтч пользователя (FIRST_MEETING ВЫДАН ВПЕРВЫЕ
        # этим мэтчем) И user.created_at не старше FAST_FRIENDS_WINDOW_HOURS.
        # Проверяем для обоих участников: у каждого свой счётчик «первое».
        fast_friends_window = timedelta(hours=FAST_FRIENDS_WINDOW_HOURS)
        now = datetime.now(timezone.utc)
        # Достаём собеседника-партнёра отдельно, чтобы знать его created_at;
        # from_user уже есть как объект, target — тоже (загружен выше как target).
        candidates_for_fast_friends: list[tuple[int, datetime]] = [
            (from_user.id, _aware(from_user.created_at)),
            (to_user_id, _aware(target.created_at)),
        ]
        fast_friends_granted: list[int] = []
        for uid, created_at in candidates_for_fast_friends:
            # Если FIRST_MEETING НЕ выдан впервые сейчас — у пользователя уже
            # были мэтчи раньше, FAST_FRIENDS он упустил.
            if uid not in first_meeting_granted:
                continue
            if now - created_at > fast_friends_window:
                continue
            if await self.achievement_service.grant(
                user_id=uid, code=AchievementCode.FAST_FRIENDS.value
            ):
                fast_friends_granted.append(uid)

        await self.matching_repo.session.commit()

        # --- Пуши после commit (контракт events: только зафиксированное) ---
        # Пуш о мэтче — обоим, каждому с именем другого (таск handoff_4 п.4.1).
        await enqueue_event(
            self.redis, match_event(user_id=from_user.id, partner_name=target.name)
        )
        await enqueue_event(
            self.redis, match_event(user_id=to_user_id, partner_name=from_user.name)
        )
        # Пуш о достижении FIRST_MEETING — тем, кому выдано впервые.
        for user_id in first_meeting_granted:
            await enqueue_event(
                self.redis,
                achievement_event(user_id=user_id, achievement_name="Первая встреча"),
            )
        # Пуши FAST_FRIENDS — тем, у кого выполнились оба условия.
        for user_id in fast_friends_granted:
            await enqueue_event(
                self.redis,
                achievement_event(user_id=user_id, achievement_name=_NAME_FAST_FRIENDS),
            )
        # Пуши OPEN_HEART / POPULAR (накопились до commit мэтча).
        for uid, name in achievement_pushes:
            await enqueue_event(
                self.redis, achievement_event(user_id=uid, achievement_name=name)
            )

        return LikeResult(is_mutual=True, match_id=match.id)

    # ------------------------------------------------------------------ #
    #  SKIP                                                              #
    # ------------------------------------------------------------------ #
    async def skip(self, *, from_user: User, skipped_user_id: int) -> SkipResult:
        """
        Скрыть кандидата из ленты на время TTL (свайп влево, «не сейчас»).

        В отличие от лайка, skip ничего не пишет в БД — только пометка в Redis.
        Это не дизлайк-«навсегда»: по истечении TTL кандидат может вернуться.
        """
        if from_user.id == skipped_user_id:
            raise SelfActionError("Нельзя скипнуть самого себя")

        await self.skip_repo.add_skip(
            user_id=from_user.id, skipped_user_id=skipped_user_id
        )

        # CHOOSY: серия скипов подряд без единого лайка. Счётчик в Redis;
        # любой лайк (в handler выше) обнуляет ключ. Выдаём ровно при достижении
        # порога (CHOOSY_THRESHOLD), повторные значения = просто скипы дальше.
        series_len = await self.counters.incr_consecutive_skips(from_user.id)
        if series_len == CHOOSY_THRESHOLD:
            # Выдаём идемпотентно. grant сам сделает коммит-нейтральную вставку
            # в текущую сессию; ниже коммит делает откатоустойчивый этой выдаче.
            granted_first = await self.achievement_service.grant(
                user_id=from_user.id, code=AchievementCode.CHOOSY.value
            )
            # skip-эндпоинт не открывает явной транзакции — flush'и
            # AchievementRepository требуют commit на сессии. Сервис мэтчинга
            # сам коммитит в like(); здесь — единичная вставка, которой тоже
            # нужен коммит для фиксации.
            await self.matching_repo.session.commit()
            if granted_first:
                await enqueue_event(
                    self.redis,
                    achievement_event(
                        user_id=from_user.id, achievement_name=_NAME_CHOOSY
                    ),
                )

        return SkipResult(skipped_user_id=skipped_user_id)


def _aware(dt: datetime) -> datetime:
    """
    Гарантировать timezone-aware datetime для сравнения с now() в UTC.

    Зачем: SQLAlchemy в зависимости от конфига колонки/драйвера может вернуть
    naive datetime (особенно при server_default=func.now()). Сравнивать naive
    с aware Python запрещает (TypeError). Считаем naive значения как UTC —
    это согласуется с server_default=NOW() в схеме TimestampMixin.
    """
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
