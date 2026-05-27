"""
Админ-эндпоинты: сводные метрики продукта.

Доступ — только для одного пользователя (ADMIN_TELEGRAM_ID), через ту же
JWT-авторизацию, что и обычные пользователи (см. deps.require_admin).
Отдельного логина/пароля нет — это намеренно для MVP.

Метрики собраны одним общим эндпоинтом /admin/metrics: фронт у нас простой
(или вовсе отсутствует), N запросов одной таблицей — избыточно. Запросы к
БД оформлены так, чтобы не было N+1: агрегаты — отдельными compact-SELECT'ами,
разрез по достижениям — одним GROUP BY с JOIN-ом в справочник.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.database import get_session
from app.models.achievement import Achievement, UserAchievement
from app.models.group import Group, GroupMember
from app.models.matching import Like, Match
from app.models.user import User
from app.schemas.admin import AchievementBreakdownItem, AdminMetrics

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/metrics",
    response_model=AdminMetrics,
    dependencies=[Depends(require_admin)],
)
async def get_metrics(
    db: AsyncSession = Depends(get_session),
) -> AdminMetrics:
    """
    Сводные метрики продукта (одним JSON-объектом).

    Включает: пользователей, активность, достижения и конверсию лайков
    в мэтчи. Все агрегаты считаются на стороне БД (func.count / func.avg)
    одним проходом по таблице — без выборки данных в Python.
    """
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)

    # --- Пользователи ---
    total_users = int(
        (await db.execute(select(func.count(User.id)))).scalar_one()
    )
    new_users_today = int(
        (
            await db.execute(
                select(func.count(User.id)).where(User.created_at >= day_ago)
            )
        ).scalar_one()
    )
    new_users_week = int(
        (
            await db.execute(
                select(func.count(User.id)).where(User.created_at >= week_ago)
            )
        ).scalar_one()
    )
    banned_users = int(
        (
            await db.execute(
                select(func.count(User.id)).where(User.is_banned.is_(True))
            )
        ).scalar_one()
    )

    # --- Активность ---
    total_likes = int(
        (await db.execute(select(func.count(Like.id)))).scalar_one()
    )
    total_matches = int(
        (await db.execute(select(func.count(Match.id)))).scalar_one()
    )
    matches_today = int(
        (
            await db.execute(
                select(func.count(Match.id)).where(Match.created_at >= day_ago)
            )
        ).scalar_one()
    )
    total_groups = int(
        (await db.execute(select(func.count(Group.id)))).scalar_one()
    )

    # Средний размер компании: считаем число участников по каждой группе,
    # потом усредняем. Один проход с подзапросом — без N+1.
    sizes_subq = (
        select(func.count(GroupMember.user_id).label("size"))
        .group_by(GroupMember.group_id)
        .subquery()
    )
    avg_group_size_raw = (
        await db.execute(select(func.avg(sizes_subq.c.size)))
    ).scalar_one()
    avg_group_size = float(avg_group_size_raw) if avg_group_size_raw is not None else 0.0

    # --- Достижения ---
    total_achievements_granted = int(
        (
            await db.execute(select(func.count(UserAchievement.user_id)))
        ).scalar_one()
    )

    # Разрез: сколько раз выдано каждое достижение. JOIN в справочник, чтобы
    # включить и нулевые (LEFT JOIN со стороны Achievement) и не делать N+1.
    breakdown_stmt = (
        select(
            Achievement.code,
            Achievement.name,
            func.count(UserAchievement.user_id),
        )
        .outerjoin(
            UserAchievement, UserAchievement.achievement_id == Achievement.id
        )
        .group_by(Achievement.id, Achievement.code, Achievement.name)
        .order_by(Achievement.id)
    )
    breakdown_rows = (await db.execute(breakdown_stmt)).all()
    achievements_breakdown = [
        AchievementBreakdownItem(code=row[0], name=row[1], count=int(row[2]))
        for row in breakdown_rows
    ]

    # --- Конверсия ---
    # Мэтч требует двух встречных лайков, поэтому числитель умножаем на 2:
    # доля лайков, поучаствовавших в мэтче. Защищаемся от деления на ноль.
    like_to_match_rate = (
        (total_matches * 2) / total_likes if total_likes > 0 else 0.0
    )

    return AdminMetrics(
        total_users=total_users,
        new_users_today=new_users_today,
        new_users_week=new_users_week,
        banned_users=banned_users,
        total_likes=total_likes,
        total_matches=total_matches,
        matches_today=matches_today,
        total_groups=total_groups,
        avg_group_size=avg_group_size,
        total_achievements_granted=total_achievements_granted,
        achievements_breakdown=achievements_breakdown,
        like_to_match_rate=like_to_match_rate,
    )
