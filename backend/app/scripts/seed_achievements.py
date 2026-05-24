"""
Seed-скрипт справочника достижений.

Наполняет таблицу `achievements` полным набором достижений. Без него витрина
пуста и выдавать нечего (grant по коду не находит запись) — поэтому скрипт
обязателен перед первым запуском и после каждого расширения списка.

Идемпотентность: повторный запуск не создаёт дублей и не трогает существующие.
Проверяем по `code` (он UNIQUE в схеме) и вставляем только отсутствующие.
То же поведение, что у seed_interests (там — по name).

Что наполняем: ВСЕ задуманные достижения, включая те, что пока не выдаются.
Невыдаваемые нужны в справочнике, чтобы витрина показывала полную карту
прогресса («ещё не открыто») — это ядро петли вовлечённости. Механики их
выдачи появятся в следующих модулях (чек-ины, отметки, признание главным).

Запуск (из папки backend/, при поднятой БД):
    python -m app.scripts.seed_achievements
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.database import async_session_factory
from app.models.achievement import Achievement
from app.models.enums import AchievementCode

# Справочник достижений: code (из AchievementCode) → имя и описание для UI.
# Тексты можно править свободно — на связь выданных достижений влияет только
# code. Порядок в списке = порядок появления в витрине.
ACHIEVEMENTS: list[dict[str, str]] = [
    {
        "code": AchievementCode.FOUNDER.value,
        "name": "Основатель",
        "description": "Заложил начало компании.",
    },
    {
        "code": AchievementCode.FIRST_MEETING.value,
        "name": "Первая встреча",
        "description": "Состоялось первое взаимное знакомство.",
    },
    {
        "code": AchievementCode.NO_BORDERS.value,
        "name": "Без границ",
        "description": "В компании собрались люди из разных городов.",
    },
    {
        "code": AchievementCode.FULL_HOUSE.value,
        "name": "Полный состав",
        "description": "Компания собрала полный состав участников.",
    },
    # --- Ниже — заведены для витрины, выдача появится позже ---
    {
        "code": AchievementCode.COMMUNITY_LEADER.value,
        "name": "Лидер комьюнити",
        "description": "Собрал самую большую компанию в сообществе.",
    },
    {
        "code": AchievementCode.IRL.value,
        "name": "В реальной жизни",
        "description": "Посетил какое-либо место всей компанией.",
    },
    {
        "code": AchievementCode.GRATITUDE.value,
        "name": "Благодарность",
        "description": "Получил отметку от другого человека за помощь.",
    },
    {
        "code": AchievementCode.SOUL.value,
        "name": "Душа компании",
        "description": "Компания единогласно признала тебя главным звеном.",
    },
]


async def seed_achievements() -> None:
    """Вставить отсутствующие достижения. Существующие не трогаем."""
    async with async_session_factory() as session:
        # Какие коды уже есть в БД.
        existing = await session.execute(select(Achievement.code))
        existing_codes = set(existing.scalars().all())

        # Добавляем только те, которых ещё нет (идемпотентность по code).
        to_add = [
            Achievement(
                code=item["code"],
                name=item["name"],
                description=item["description"],
            )
            for item in ACHIEVEMENTS
            if item["code"] not in existing_codes
        ]

        if not to_add:
            print("Достижения уже наполнены — добавлять нечего.")
            return

        session.add_all(to_add)
        await session.commit()
        print(f"Добавлено достижений: {len(to_add)}")
        for achievement in to_add:
            print(f"  + {achievement.code}: {achievement.name}")


if __name__ == "__main__":
    asyncio.run(seed_achievements())
