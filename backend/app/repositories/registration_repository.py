"""
Репозиторий регистрации — слой доступа к БД (только запросы, без бизнес-логики).

Отвечает за:
  1. Проверку, есть ли уже пользователь с таким telegram_id (повторная регистрация).
  2. Проверку, что переданные interest_ids реально существуют в справочнике.
  3. Создание User вместе со связями user_interests (всё одним коммитом — делает сервис).

Бизнес-решения (откуда взять фото, что считать «уже зарегистрирован») — НЕ здесь,
а в сервисном слое. Репозиторий лишь выполняет запросы.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interest import Interest
from app.models.user import User


class RegistrationRepository:
    """Запросы к БД для регистрации пользователя."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        """Найти пользователя по telegram_id (None — если ещё не регистрировался)."""
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_existing_interests(self, interest_ids: list[int]) -> list[Interest]:
        """
        Вернуть из справочника только реально существующие интересы по id.

        Сервис сравнит длину результата с запросом: если что-то не найдено —
        значит фронт прислал несуществующий interest_id (отвергаем регистрацию).
        Возвращаем объекты Interest, а не id — их сразу привяжем к User.
        """
        if not interest_ids:
            return []
        result = await self.session.execute(
            select(Interest).where(Interest.id.in_(interest_ids))
        )
        return list(result.scalars().all())

    async def create_user(
        self,
        *,
        telegram_id: int,
        name: str,
        age: int,
        about: str,
        photo_file_id: str,
        city: str,
        interests: list[Interest],
    ) -> User:
        """
        Создать пользователя и привязать интересы (в рамках текущей сессии).

        Коммит здесь НЕ делается — это ответственность сервиса (единая точка
        фиксации транзакции, как в остальных модулях проекта). flush нужен,
        чтобы получить сгенерированный user.id до возврата.
        """
        user = User(
            telegram_id=telegram_id,
            name=name,
            age=age,
            about=about,
            photo_file_id=photo_file_id,
            city=city,
        )
        # Привязка интересов через relationship User.interests (secondary-таблица
        # user_interests заполнится автоматически при коммите).
        user.interests = interests

        self.session.add(user)
        # flush отправляет INSERT в БД и проставляет user.id, но транзакцию
        # не закрывает — итоговый commit сделает сервис.
        await self.session.flush()
        return user
