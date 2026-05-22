"""
Подключение к базе данных: async-движок и фабрика сессий.

Используется и приложением (FastAPI, бот), и Alembic-миграциями.
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import DATABASE_URL

# Движок — пул соединений на всё приложение. Создаётся один раз.
# echo=False: не логировать каждый SQL-запрос (включить True при отладке).
engine = create_async_engine(DATABASE_URL, echo=False)

# Фабрика сессий. expire_on_commit=False — объекты остаются доступны после commit
# (иначе обращение к их полям после commit вызвало бы новый запрос к БД).
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Выдаёт сессию БД и гарантированно закрывает её после использования.

    Предназначена для внедрения зависимостей (например, FastAPI Depends):
        async def endpoint(session: AsyncSession = Depends(get_session)): ...
    """
    async with async_session_factory() as session:
        yield session
