"""
Backfill EARLY_BIRD для уже зарегистрированных пользователей.

Зачем: достижение EARLY_BIRD появилось в коде ПОСЛЕ того, как первая партия
пользователей зарегистрировалась. Автоматическая выдача в registration_service
их не зацепит (они уже в БД). Этот скрипт выдаёт им «Раннюю пташку» вручную.

Что делает:
  1. Берёт всех User'ов из БД.
  2. Для каждого пытается выдать AchievementCode.EARLY_BIRD через
     AchievementService.grant() (идемпотентно: повторный запуск не дублирует).
  3. Выводит сводку «выдано / уже было / итого».
  4. НЕ шлёт пуши в events-очередь — это backfill, не свежее событие. Иначе
     5 человек получили бы пуш о «достижении», как будто только что заработали.

Почему всем подряд, без проверки LAUNCH_DATE:
  Скрипт запускают вручную для уже существующей когорты — они и есть
  «первая волна». Дата запуска (LAUNCH_DATE) в .env используется только для
  автоматической выдачи новым регистрациям; для backfill это лишняя проверка
  (мы и так знаем, что эти 5 — ранние).

Запуск (из контейнера API):
    docker compose exec api python -m app.scripts.backfill_early_bird

Идемпотентность: безопасно запускать повторно, даже после новых регистраций.
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.database import async_session_factory
from app.models.enums import AchievementCode
from app.models.user import User
from app.repositories.achievement_repository import AchievementRepository
from app.services.achievement_service import AchievementService


async def backfill_early_bird() -> None:
    """Выдать EARLY_BIRD всем существующим пользователям. Идемпотентно."""
    async with async_session_factory() as session:
        # Берём всех (без is_banned-фильтра: забаненный пользователь тоже
        # часть истории; если разбанят — достижение уже будет).
        result = await session.execute(select(User.id, User.name))
        rows = list(result.all())

        if not rows:
            print("В БД нет пользователей. Backfill не нужен.")
            return

        service = AchievementService(
            achievement_repo=AchievementRepository(session)
        )

        granted: list[tuple[int, str]] = []
        already_had: list[tuple[int, str]] = []
        for user_id, name in rows:
            was_first_time = await service.grant(
                user_id=user_id,
                code=AchievementCode.EARLY_BIRD.value,
            )
            if was_first_time:
                granted.append((user_id, name))
            else:
                already_had.append((user_id, name))

        # Единый commit на всю партию — атомарно. Если упадёт — ничего не
        # выдалось, можно повторить.
        await session.commit()

        print(f"Всего пользователей: {len(rows)}")
        print(f"Выдано EARLY_BIRD впервые: {len(granted)}")
        for uid, name in granted:
            print(f"  + #{uid} {name}")
        print(f"Уже было: {len(already_had)}")
        for uid, name in already_had:
            print(f"  · #{uid} {name}")


if __name__ == "__main__":
    asyncio.run(backfill_early_bird())
