"""
Схемы админ-эндпоинтов: метрики продукта.

Один JSON-объект на все цифры (users / activity / achievements / conversion):
проще читать в Postman и проще отрисовать таблицей. Если позже появится
полноценная дашборд-страница — добавим срезы отдельными эндпоинтами, но базовые
агрегаты останутся здесь.
"""
from __future__ import annotations

from pydantic import BaseModel


class AchievementBreakdownItem(BaseModel):
    """Сколько раз выдано конкретное достижение (по справочнику)."""

    code: str
    name: str
    count: int


class AdminMetrics(BaseModel):
    """Сводные метрики продукта для админ-панели."""

    # --- Пользователи ---
    total_users: int
    new_users_today: int  # за последние 24 часа
    new_users_week: int  # за последние 7 дней
    banned_users: int

    # --- Активность ---
    total_likes: int
    total_matches: int
    matches_today: int  # за последние 24 часа
    total_groups: int
    avg_group_size: float  # средний размер компании

    # --- Достижения ---
    total_achievements_granted: int
    achievements_breakdown: list[AchievementBreakdownItem]

    # --- Конверсия ---
    # like_to_match_rate = total_matches * 2 / total_likes (умножаем на 2,
    # потому что мэтч — это два встречных лайка).
    like_to_match_rate: float
