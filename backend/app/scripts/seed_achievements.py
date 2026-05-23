"""
Seed-скрипт справочника достижений (таблица `achievements`).

Наполняет справочник достижениями. Без него выдавать технически нечего
(AchievementService.grant не найдёт код и тихо пропустит выдачу) — поэтому
скрипт обязателен перед первым запуском, как seed_interests.

Чем отличается от seed_interests: здесь UPSERT, а не только вставка.
Повторный прогон ОБНОВЛЯЕТ name/description у существующих кодов. Смысл:
ты редактируешь тексты ниже, перезапускаешь скрипт — и витрина показывает
новые формулировки. Менять справочник можно без миграций и без правки логики.

  • code   — технический идентификатор, по нему код выдаёт достижение.
             Менять НЕ нужно (на него завязана логика). Уникален.
  • name / description — то, что видит пользователь. Меняй свободно.

Как добавить достижение позже:
  1) Если оно выдаётся автоматически — добавь код в AchievementCode (enums.py)
     и хук в место события. Если только для витрины — этого не нужно.
  2) Добавь строку в ACHIEVEMENTS ниже.
  3) Прогони скрипт.

Запуск (из папки backend/, при поднятой БД):
    python -m app.scripts.seed_achievements
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.database import async_session_factory
from app.models.achievement import Achievement

# --------------------------------------------------------------------- #
#  СПРАВОЧНИК ДОСТИЖЕНИЙ — редактируй здесь                             #
# --------------------------------------------------------------------- #
# Формат строки: (code, name, description).
# Сейчас наполнены только 4 достижения с автоматической выдачей.
# Остальные (визиты, благодарности, «душа компании») добавишь сюда позже,
# когда под них появятся фичи и ты убедишься, что продукт работает.
ACHIEVEMENTS: list[tuple[str, str, str]] = [
    (
        "FOUNDER",
        "Основатель",
        "Заложил начало компании — создал её из своего знакомства.",
    ),
    (
        "FIRST_MEET",
        "Первая встреча",
        "Провёл первое знакомство один на один.",
    ),
    (
        "FULL_HOUSE",
        "Полный состав",
        "Собрал компанию из 8 человек — главная цель игры пройдена.",
    ),
    (
        "NO_BORDERS",
        "Без границ",
        "Собрал компанию, в которой есть люди из двух и более городов.",
    ),
]


async def seed_achievements() -> None:
    """Вставить отсутствующие достижения, обновить тексты у существующих (upsert)."""
    async with async_session_factory() as session:
        existing_rows = await session.execute(select(Achievement))
        existing_by_code = {a.code: a for a in existing_rows.scalars().all()}

        inserted = 0
        updated = 0
        for code, name, description in ACHIEVEMENTS:
            current = existing_by_code.get(code)
            if current is None:
                session.add(
                    Achievement(code=code, name=name, description=description)
                )
                inserted += 1
                print(f"  + {code} — {name}")
            elif current.name != name or current.description != description:
                current.name = name
                current.description = description
                updated += 1
                print(f"  ~ {code} — обновлён текст")

        if inserted == 0 and updated == 0:
            print("Справочник достижений актуален — менять нечего.")
            return

        await session.commit()
        print(f"Готово. Добавлено: {inserted}, обновлено: {updated}.")


if __name__ == "__main__":
    asyncio.run(seed_achievements())
