"""
Схемы модуля «Достижения» — контракт ответов API (Pydantic v2).

Используются витриной: фронтенд Mini App показывает полученные достижения и
ещё закрытые цели. Схемы описывают форму JSON, который отдаёт роутер.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AchievementCard(BaseModel):
    """
    Одно достижение в витрине пользователя.

    earned=False означает «ещё не получено» — карточка показывается как закрытая
    цель (earned_at при этом None). earned=True — получено, earned_at заполнено.
    """

    code: str          # технический код (для иконок/логики на фронте)
    name: str          # что видит пользователь
    description: str   # условие/описание
    earned: bool       # получено ли
    earned_at: datetime | None = None  # когда получено (None, если ещё нет)


class AchievementShowcase(BaseModel):
    """Витрина целиком: список достижений + счётчики для прогресс-бара."""

    achievements: list[AchievementCard]
    earned_count: int  # сколько получено
    total_count: int   # сколько всего в справочнике
