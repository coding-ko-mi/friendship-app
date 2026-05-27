"""
Хранилище skip-пометок ленты (Redis).

Когда пользователь свайпает кандидата влево («не сейчас»), мы прячем кандидата
из его ленты на DISCOVERY_SKIP_TTL_HOURS часов. По истечении TTL кандидат
снова может всплыть — это намеренно (анкеты обновляются, второй шанс полезен).

Почему Redis, а не таблица в БД:
  • skip — это эфемерные данные с истечением, ровно под TTL Redis;
  • не засоряем БД и не плодим миграции под временные пометки;
  • Redis уже в стеке проекта.

Структура: Redis ZSET (sorted set) с ключом skip:{user_id}.
  • members  = id скипнутых пользователей;
  • score    = unix-таймстамп ИСТЕЧЕНИЯ конкретного скипа.

Зачем ZSET, а не SET с TTL на весь ключ: SET-вариант продлевал бы TTL на
ВЕСЬ сет при каждом новом скипе — старые скипы «возрождались». В ZSET у
каждого скипа индивидуальный срок: при чтении фильтруем по score >= now,
истёкшие подметаем ZREMRANGEBYSCORE. Это лёгкая бухгалтерия — добавление
O(log n), чтение O(log n + k), уборка O(log n + k).
"""
from __future__ import annotations

from time import time

from redis.asyncio import Redis

from app.config import DISCOVERY_SKIP_TTL_HOURS


class SkipRepository:
    """Skip-пометки ленты в Redis с индивидуальным TTL на каждую пару."""

    def __init__(self, redis: Redis) -> None:
        self.redis = redis
        # TTL в секундах. Считаем один раз при создании репозитория.
        self._ttl_seconds = DISCOVERY_SKIP_TTL_HOURS * 60 * 60

    @staticmethod
    def _key(user_id: int) -> str:
        """Ключ Redis для skip-ZSET конкретного пользователя."""
        return f"skip:{user_id}"

    async def add_skip(self, *, user_id: int, skipped_user_id: int) -> None:
        """
        Пометить кандидата как скипнутого на DISCOVERY_SKIP_TTL_HOURS часов.

        Записываем skipped_user_id в ZSET со score = «когда этот скип истечёт».
        Если того же кандидата скипнули повторно — ZADD просто обновит score
        (т.е. сдвинет именно его срок, не затронув остальные).
        """
        key = self._key(user_id)
        expires_at = time() + self._ttl_seconds
        await self.redis.zadd(key, {str(skipped_user_id): expires_at})

    async def get_skipped_ids(self, user_id: int) -> list[int]:
        """
        ID актуально скипнутых кандидатов (исключаем из ленты).

        Под капотом:
          1. Сначала чистим истёкшие — у них score < now.
          2. Затем читаем оставшихся.
        Уборка идёт здесь, а не отдельным фоном: чтение и так O(log n + k),
        и без неё ZSET тихо разрастался бы. Сама операция точечная (ZREMRANGEBYSCORE).
        """
        key = self._key(user_id)
        now = time()
        # 1. Снять истёкшие (score < now).
        await self.redis.zremrangebyscore(key, min=0, max=now - 1)
        # 2. Прочитать актуальные (всё что выше now). +inf — все живые.
        members = await self.redis.zrangebyscore(key, min=now, max="+inf")
        return [int(m) for m in members]
