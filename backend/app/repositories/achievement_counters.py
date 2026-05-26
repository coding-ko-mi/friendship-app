"""
Счётчики и эфемерные состояния для достижений (Redis).

Зачем отдельный модуль (а не в achievement_repository): счётчики живут в Redis,
а не в БД. Класть их в существующий AchievementRepository (который работает с
SQLAlchemy-сессией) — смешение слоёв. Здесь — тонкая обёртка над Redis-командами
с понятными именами и в одном месте, чтобы вся «бухгалтерия счётчиков» не
размазалась по сервисам.

Хранимые сущности:
  • likes_given:{user_id}         — счётчик исходящих лайков (для OPEN_HEART)
  • likes_received:{user_id}      — счётчик входящих лайков (для POPULAR)
  • consecutive_skips:{user_id}   — скипы подряд без лайка (для CHOOSY)
  • votes_cast:{user_id}          — счётчик голосований (для FAIR_JUDGE)
  • request_initiator:{request_id} — кто подал заявку (для RECRUITER/DIPLOMAT)

Все ключи без TTL по умолчанию (это исторические счётчики). Исключение —
request_initiator: ему ставится недельный TTL, потому что голосование заведомо
завершается раньше, а зависшие заявки нам не интересны.

Совместимость с decode_responses=True: Redis-клиент в проекте сконфигурирован
возвращать строки (см. SkipRepository), поэтому INCR-результат и GET строковые
— приводим к int сами.
"""
from __future__ import annotations

from redis.asyncio import Redis


# TTL для request_initiator: неделя — заведомо больше реального срока жизни
# голосования. Если за неделю заявка не закрылась, она всё равно протухает
# логически (бизнес-правил «бесконечного голосования» нет).
_REQUEST_INITIATOR_TTL_SECONDS = 7 * 24 * 60 * 60


class AchievementCounters:
    """Тонкая обёртка над Redis для счётчиков-достижений и атрибутов заявок."""

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    # ------------------------------------------------------------------ #
    #  СЧЁТЧИКИ ЛАЙКОВ                                                   #
    # ------------------------------------------------------------------ #
    async def incr_likes_given(self, user_id: int) -> int:
        """Увеличить и вернуть счётчик исходящих лайков пользователя."""
        return int(await self.redis.incr(f"ach:likes_given:{user_id}"))

    async def incr_likes_received(self, user_id: int) -> int:
        """Увеличить и вернуть счётчик входящих лайков пользователя."""
        return int(await self.redis.incr(f"ach:likes_received:{user_id}"))

    # ------------------------------------------------------------------ #
    #  ПОСЛЕДОВАТЕЛЬНЫЕ СКИПЫ                                            #
    # ------------------------------------------------------------------ #
    async def incr_consecutive_skips(self, user_id: int) -> int:
        """Скип засчитывается в серию. Возвращает текущую длину серии."""
        return int(await self.redis.incr(f"ach:consecutive_skips:{user_id}"))

    async def reset_consecutive_skips(self, user_id: int) -> None:
        """
        Прервать серию (вызывается при любом лайке).

        Серия — это «20 подряд без единого лайка». Поэтому первый же лайк
        сбрасывает счётчик в 0 (физически — удаляем ключ).
        """
        await self.redis.delete(f"ach:consecutive_skips:{user_id}")

    # ------------------------------------------------------------------ #
    #  СЧЁТЧИК ГОЛОСОВАНИЙ                                               #
    # ------------------------------------------------------------------ #
    async def incr_votes_cast(self, user_id: int) -> int:
        """Каждое поданное голосование увеличивает счётчик голосующего."""
        return int(await self.redis.incr(f"ach:votes_cast:{user_id}"))

    # ------------------------------------------------------------------ #
    #  ИНИЦИАТОР ЗАЯВКИ (RECRUITER / DIPLOMAT)                           #
    # ------------------------------------------------------------------ #
    # Кто подал invite/merge — нужно при финализации, чтобы выдать
    # RECRUITER/DIPLOMAT именно подателю. В БД хранить отдельной колонкой —
    # потребует миграцию; здесь решаем через Redis с TTL.
    async def set_request_initiator(
        self, *, request_id: int, user_id: int
    ) -> None:
        """Сохранить инициатора заявки на время жизни голосования."""
        await self.redis.set(
            f"ach:request_initiator:{request_id}",
            user_id,
            ex=_REQUEST_INITIATOR_TTL_SECONDS,
        )

    async def get_request_initiator(self, request_id: int) -> int | None:
        """Достать инициатора заявки. None, если ключ протух или его не было."""
        value = await self.redis.get(f"ach:request_initiator:{request_id}")
        return int(value) if value is not None else None
