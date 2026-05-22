"""
Подключение к Redis: единый async-клиент на всё приложение.

Заводится впервые в модуле «Бэкенд: мэтчинг» — здесь Redis впервые понадобился
(хранение skip-пометок ленты с TTL). Дальше тем же клиентом будут пользоваться
другие модули (FSM-сторадж бота, кэш подборок, антиспам) — отдельных подключений
плодить не нужно.

Паттерн повторяет app/database.py: один клиент-пул на процесс + зависимость
для FastAPI Depends.
"""
from collections.abc import AsyncGenerator

from redis.asyncio import Redis, from_url

from app.config import REDIS_URL

# Один клиент на всё приложение (внутри — пул соединений). Создаётся один раз.
# decode_responses=True: Redis отдаёт строки, а не bytes — удобнее работать
# с ключами/значениями как с обычным текстом.
redis_client: Redis = from_url(REDIS_URL, decode_responses=True)


async def get_redis() -> AsyncGenerator[Redis, None]:
    """
    Выдаёт Redis-клиент для внедрения зависимостей (FastAPI Depends):
        async def endpoint(redis: Redis = Depends(get_redis)): ...

    Клиент общий и закрывать его на каждый запрос не нужно (пул живёт всё
    время работы приложения), поэтому просто отдаём ссылку на него.
    """
    yield redis_client
