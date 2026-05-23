"""
Сервис мэтчинга — бизнес-логика модуля (сценарий А: одиночка ↔ одиночка).

Здесь принимаются продуктовые решения:
  • как собрать ленту (фильтры + скоринг по интересам);
  • что происходит при лайке (создать лайк, проверить встречный → мэтч);
  • канонический порядок пары в Match (user_a_id < user_b_id);
  • как работает skip.

Транспорт (HTTP) и доступ к БД сюда не лезут — сервис оркеструет репозитории
и возвращает готовые схемы. Уведомление о мэтче НЕ отправляется здесь:
сервис лишь возвращает is_mutual + match_id, а пуш делает модуль «Бот».

Достижение FIRST_MEET («Первая встреча») выдаётся здесь — обоим участникам при
взаимном мэтче, на той же сессии (в одной транзакции с созданием Match).
Идемпотентно: у каждого пользователя оно появится только при первом мэтче.
"""
from __future__ import annotations

from app.config import DISCOVERY_PAGE_SIZE
from app.models.enums import AchievementCode
from app.models.user import User
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
    ) -> None:
        self.matching_repo = matching_repo
        self.skip_repo = skip_repo

    # ------------------------------------------------------------------ #
    #  ВСПОМОГАТЕЛЬНОЕ                                                   #
    # ------------------------------------------------------------------ #
    def _achievement_service(self) -> AchievementService:
        """
        Собрать сервис достижений на ТЕКУЩЕЙ сессии.

        Тот же session, что и у matching_repo → выдача FIRST_MEET идёт в одной
        транзакции с созданием Match. Конструктор и роутер не меняются.
        """
        return AchievementService(
            repo=AchievementRepository(self.matching_repo.session)
        )

    async def _grant_first_meet(self, user_a_id: int, user_b_id: int) -> None:
        """
        Выдать «Первую встречу» (FIRST_MEET) обоим участникам мэтча.

        Идемпотентно: grant_many выдаст достижение только тем, у кого его ещё
        нет. Поэтому при втором и последующих мэтчах ничего не задвоится.
        """
        await self._achievement_service().grant_many(
            user_ids=(user_a_id, user_b_id), code=AchievementCode.FIRST_MEET
        )

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
        my_interest_ids = await self.matching_repo.get_user_interest_ids(
            current_user.id
        )

        liked_ids = await self.matching_repo.get_liked_user_ids(current_user.id)
        skipped_ids = await self.skip_repo.get_skipped_ids(current_user.id)
        excluded_ids = list(set(liked_ids) | set(skipped_ids))

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
          • если встречный лайк уже есть → создаём Match (канонический порядок)
            и выдаём обоим достижение FIRST_MEET.

        Возвращает is_mutual (+ match_id, если мэтч). Пуш о мэтче — модуль «Бот».
        """
        if from_user.id == to_user_id:
            raise SelfActionError("Нельзя лайкнуть самого себя")

        target = await self.matching_repo.get_target_user(to_user_id)
        if target is None or target.is_banned:
            raise TargetNotFoundError("Пользователь не найден")

        already_liked = await self.matching_repo.like_exists(
            from_user_id=from_user.id, to_user_id=to_user_id
        )
        if not already_liked:
            await self.matching_repo.add_like(
                from_user_id=from_user.id, to_user_id=to_user_id
            )

        reciprocal = await self.matching_repo.like_exists(
            from_user_id=to_user_id, to_user_id=from_user.id
        )

        if not reciprocal:
            await self.matching_repo.session.commit()
            return LikeResult(is_mutual=False)

        # --- Взаимный лайк: создаём (или находим) Match ---
        # Канонический порядок: меньший id всегда user_a.
        user_a_id, user_b_id = sorted((from_user.id, to_user_id))

        existing = await self.matching_repo.match_exists(
            user_a_id=user_a_id, user_b_id=user_b_id
        )
        if existing is not None:
            match_id = existing.id
        else:
            match = await self.matching_repo.add_match(
                user_a_id=user_a_id, user_b_id=user_b_id
            )
            match_id = match.id

        # Достижение «Первая встреча» обоим — в той же транзакции (идемпотентно).
        await self._grant_first_meet(from_user.id, to_user_id)

        await self.matching_repo.session.commit()
        return LikeResult(is_mutual=True, match_id=match_id)

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
        return SkipResult(skipped_user_id=skipped_user_id)
