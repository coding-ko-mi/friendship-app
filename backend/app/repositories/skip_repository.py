"""
Хранилище skip-пометок ленты (Redis).

Когда пользователь свайпает кандидата влево («не сейчас»), мы прячем кандидата
из его ленты на DISCOVERY_SKIP_TTL_DAYS дней. По истечении TTL кандидат снова
может всплыть — это намеренно (анкеты и интересы меняются, второй шанс полезен).

Почему Redis, а не таблица в БД:
  • skip — это эфемерные данные с истечением, ровно под TTL Redis;
  • не засоряем БД и не плодим миграции под временные пометки;
  • Redis уже в стеке проекта.

Структура ключа: skip:{user_id} — это Redis SET с id скипнутых кандидатов.
TTL ставится на весь ключ-сет и продлевается при каждом новом skip.
"""
from __future__ import annotations

from redis.asyncio import Redis

from app.config import DISCOVERY_SKIP_TTL_DAYS


class SkipRepository:
    """Skip-пометки ленты в Redis."""

    def __init__(self, redis: Redis) -> None:
        self.redis = redis
        # TTL в секундах. Считаем один раз при создании репозитория.
        self._ttl_seconds = DISCOVERY_SKIP_TTL_DAYS * 24 * 60 * 60

    @staticmethod
    def _key(user_id: int) -> str:
        """Ключ Redis для skip-сета конкретного пользователя."""
        return f"skip:{user_id}"

    async def add_skip(self, *, user_id: int, skipped_user_id: int) -> None:
        """
        Пометить кандидата как скипнутого и продлить TTL всего сета.

        Продление TTL при каждом skip означает: пока человек активно листает,
        его скипы держатся; перестал пользоваться — через TTL сет очистится сам.
        """
        key = self._key(user_id)
        await self.redis.sadd(key, skipped_user_id)
        await self.redis.expire(key, self._ttl_seconds)

    async def get_skipped_ids(self, user_id: int) -> list[int]:
        """ID всех актуально скипнутых кандидатов (для исключения из ленты)."""
        key = self._key(user_id)
        members = await self.redis.smembers(key)
        # decode_responses=True уже отдаёт строки — приводим к int.
        return [int(m) for m in members]
