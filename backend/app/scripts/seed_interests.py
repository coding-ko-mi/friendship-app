"""
Seed-скрипт справочника интересов.

Наполняет таблицу `interests` стартовым набором категорий. Без него лента
пуста (мэтчить не по чему) — поэтому скрипт обязателен перед первым запуском.

Идемпотентность: повторный запуск не создаёт дублей. Проверяем по name
(оно UNIQUE в схеме) и вставляем только отсутствующие. Можно безопасно
прогонять после каждого расширения списка.

Запуск (из папки backend/, при поднятой БД):
    python -m app.scripts.seed_interests
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.database import async_session_factory
from app.models.interest import Interest

# Стартовый набор интересов (22 категории, выбраны под СПб / 18–40).
# Расширяется простым дополнением списка — миграция не нужна, схема не меняется.
INTERESTS: list[str] = [
    "Путешествия",
    "Рыбалка, охота и туризм",
    "Тренажёрный зал и бег",
    "Йога",
    "Видеоигры",
    "Настольные игры",
    "Кино и сериалы",
    "Совместное обучение",
    "Аниме",
    "Концерты и живая музыка",
    "Кулинария и готовка",
    "Кофейни и рестораны",
    "Фотография и видео",
    "Программирование",
    "Бизнес и предпринимательство",
    "Автомобили и тюнинг",
    "Книги и чтение",
    "Психология и осознанность",
    "Бары и ночная жизнь",
    "Здоровый образ жизни",
    "Инвестиции и финансы",
    "Личностный рост и саморазвитие",
]


async def seed_interests() -> None:
    """Вставить отсутствующие интересы. Существующие не трогаем."""
    async with async_session_factory() as session:
        # Какие интересы уже есть в БД (по name).
        existing = await session.execute(select(Interest.name))
        existing_names = set(existing.scalars().all())

        # Добавляем только те, которых ещё нет.
        to_add = [Interest(name=n) for n in INTERESTS if n not in existing_names]

        if not to_add:
            print("Интересы уже наполнены — добавлять нечего.")
            return

        session.add_all(to_add)
        await session.commit()
        print(f"Добавлено интересов: {len(to_add)}")
        for interest in to_add:
            print(f"  + {interest.name}")


if __name__ == "__main__":
    asyncio.run(seed_interests())
