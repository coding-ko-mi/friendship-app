"""
UserRepository — запросы к существующей таблице users.

Пользователи создаются через Telegram-бот (aiogram).
API только читает и проверяет — не создаёт напрямую.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        """Найти пользователя по Telegram ID. Вызывается при авторизации."""
        result = await self.db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> User | None:
        """Найти пользователя по внутреннему ID. Вызывается при проверке токена."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
