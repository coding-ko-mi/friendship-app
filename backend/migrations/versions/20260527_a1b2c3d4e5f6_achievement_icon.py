"""Добавление колонки icon в таблицу achievements.

Иконка используется в UI: в чужой анкете (карточке кандидата) и в витрине
достижений. Раньше иконка хранилась только на фронте, теперь — общий
источник правды в БД. Дефолт ⭐ для существующих записей, чтобы UI не падал
до прогона seed.

Revision ID: a1b2c3d4e5f6
Revises: 7feaadaf12bd
Create Date: 2026-05-27
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "7feaadaf12bd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "achievements",
        sa.Column(
            "icon",
            sa.String(length=16),
            nullable=False,
            server_default="⭐",
        ),
    )


def downgrade() -> None:
    op.drop_column("achievements", "icon")
