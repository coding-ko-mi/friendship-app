"""
Схемы модуля «Достижения» — контракт ответа API для витрины Mini App.

Витрина показывает ВЕСЬ справочник достижений с флагом, получено ли каждое
конкретным пользователем. Это даёт UX «прогресс + что ещё можно получить» —
ядро геймификации (петля: прогресс → достижение → желание нового прогресса).
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AchievementCard(BaseModel):
    """
    Одно достижение в витрине.

    code/name/description — из справочника (что это за достижение).
    earned — получил ли его текущий пользователь.
    earned_at — когда получил (None, если ещё не получено).
    """

    # from_attributes: разрешаем собирать схему из ORM-объектов и произвольных
    # объектов с атрибутами (мы наполняем её в сервисе вручную).
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    description: str
    earned: bool
    earned_at: datetime | None = None


class AchievementsResponse(BaseModel):
    """
    Ответ витрины: список всех достижений с флагом earned + сводка прогресса.

    earned_count / total — чтобы фронт показал «3 из 8» без пересчёта на клиенте.
    """

    items: list[AchievementCard]
    earned_count: int
    total: int
