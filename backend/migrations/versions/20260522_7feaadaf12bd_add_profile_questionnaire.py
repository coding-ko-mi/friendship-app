"""Добавление таблиц profiles и questionnaires.

Ревизия поверх начальной схемы (11 таблиц).
Добавляет 2 новые таблицы для FastAPI-слоя (Mini App).

Revision ID: 7feaadaf12bd
Revises: 357e7b0dc368
Create Date: 2026-05-22
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "7feaadaf12bd"
down_revision: Union[str, None] = "357e7b0dc368"  # начальная миграция из чата «БД»
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Таблица profiles
    # ------------------------------------------------------------------
    # Дополняет существующую таблицу users полями для Mini App:
    # пол, геокоординаты, дополнительные фото, видимость в поиске.
    # Базовые поля (name, age, about, city, photo_file_id) остаются в users.
    op.create_table(
        "profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        # FK на users.id (Integer — совпадает с PK существующей таблицы)
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(64), nullable=True),
        # gender хранится как строка — легко расширять без DDL
        sa.Column("gender", sa.String(10), nullable=True),
        # Точные координаты для расчёта расстояния между пользователями.
        # Наружу отдаём только округлённое гео (~1 км).
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
        # Доп. фото через разделитель "|" — простое решение для MVP.
        sa.Column("extra_photos_urls", sa.Text(), nullable=True),
        sa.Column(
            "is_visible",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_profiles_user_id"),
    )
    op.create_index("ix_profiles_user_id", "profiles", ["user_id"], unique=True)

    # ------------------------------------------------------------------
    # Таблица questionnaires
    # ------------------------------------------------------------------
    # Данные для мэтчинга: цель, образ жизни, предпочтения.
    # Интересы НЕ дублируются — используется существующая user_interests.
    op.create_table(
        "questionnaires",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        # Что ищет: группу (group), друзей 1-на-1 (friends), оба (both)
        sa.Column("looking_for", sa.String(20), nullable=True),
        # Образ жизни: never / sometimes / often
        sa.Column("smoking", sa.String(20), nullable=True),
        sa.Column("alcohol", sa.String(20), nullable=True),
        sa.Column("sport", sa.String(20), nullable=True),
        # Предпочтения партнёра
        sa.Column("partner_age_min", sa.Integer(), nullable=True),
        sa.Column("partner_age_max", sa.Integer(), nullable=True),
        sa.Column("partner_max_distance_km", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_questionnaires_user_id"),
    )
    op.create_index(
        "ix_questionnaires_user_id", "questionnaires", ["user_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_questionnaires_user_id", table_name="questionnaires")
    op.drop_table("questionnaires")
    op.drop_index("ix_profiles_user_id", table_name="profiles")
    op.drop_table("profiles")
