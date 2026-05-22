"""Геймификация: справочник достижений и полученные достижения пользователей."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class Achievement(Base):
    """
    Справочник достижений. Заполняется заранее.

    code — технический неизменяемый идентификатор (FOUNDER, FULL_HOUSE...),
    по нему код выдаёт достижения. name/description — то, что видит пользователь.
    """

    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class UserAchievement(Base):
    """
    Полученное достижение. Ассоциативный объект «пользователь ↔ достижение».

    Модель-класс (а не Table), потому что есть поле earned_at.
    Первичный ключ — пара (user_id, achievement_id): одно достижение
    выдаётся пользователю не более одного раза.

    «Основатель» живёт здесь: при создании компании пользователь получает
    достижение с кодом FOUNDER — это исторический факт о человеке,
    не привязанный к конкретной группе.
    """

    __tablename__ = "user_achievements"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    achievement_id: Mapped[int] = mapped_column(
        ForeignKey("achievements.id", ondelete="CASCADE"), primary_key=True
    )
    earned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="achievement_links")
    achievement: Mapped[Achievement] = relationship()
