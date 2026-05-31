"""chat module: message_thread_id + drop unique telegram_chat_id

Модуль «Чатинг» (вариант Б — Hub-супергруппа с топиками).

Изменения схемы groups:
  • снять UNIQUE с telegram_chat_id — теперь это ID общего Hub-чата, одинаковый
    у всех компаний (уникальность ломала бы вторую же компанию);
  • добавить message_thread_id — ID топика компании внутри Hub.

Связка «компания → её тред» = пара (telegram_chat_id, message_thread_id).

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-28
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Снять автоимённый UNIQUE-констрейнт с telegram_chat_id.
    #    Имя у безымянного UniqueConstraint в PostgreSQL — "<table>_<col>_key".
    op.drop_constraint(
        "groups_telegram_chat_id_key", "groups", type_="unique"
    )
    # 2. Добавить колонку треда (nullable: компания живёт до создания топика).
    op.add_column(
        "groups",
        sa.Column("message_thread_id", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    # Откат в обратном порядке.
    op.drop_column("groups", "message_thread_id")
    op.create_unique_constraint(
        "groups_telegram_chat_id_key", "groups", ["telegram_chat_id"]
    )
