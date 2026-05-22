"""Мэтчинг «одиночка ↔ одиночка»: лайки и подтверждённые мэтчи (сценарий А)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class Like(Base, TimestampMixin):
    """
    Лайк одного одиночки другому.

    Когда оба пользователя лайкнули друг друга (есть встречный лайк) —
    создаётся Match и открывается чат 1-на-1.
    """

    __tablename__ = "likes"
    __table_args__ = (
        # Нельзя поставить лайк одному и тому же человеку дважды.
        UniqueConstraint("from_user_id", "to_user_id", name="uq_like_pair"),
        # Нельзя лайкнуть самого себя.
        CheckConstraint("from_user_id <> to_user_id", name="ck_like_not_self"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    to_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Два внешних ключа на одну таблицу users -> явно указываем foreign_keys,
    # иначе SQLAlchemy не поймёт, какая связь по какому столбцу.
    from_user: Mapped[User] = relationship(foreign_keys=[from_user_id])
    to_user: Mapped[User] = relationship(foreign_keys=[to_user_id])


class Match(Base, TimestampMixin):
    """
    Подтверждённый взаимный интерес двух одиночек -> открывает чат 1-на-1.

    Пара хранится в каноническом порядке (user_a_id < user_b_id).
    Это вместе с UniqueConstraint гарантирует, что пара (A, B) и (B, A)
    не задвоится — в БД будет ровно одна строка на пару.
    """

    __tablename__ = "matches"
    __table_args__ = (
        UniqueConstraint("user_a_id", "user_b_id", name="uq_match_pair"),
        CheckConstraint("user_a_id < user_b_id", name="ck_match_canonical_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_a_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_b_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    user_a: Mapped[User] = relationship(foreign_keys=[user_a_id])
    user_b: Mapped[User] = relationship(foreign_keys=[user_b_id])
