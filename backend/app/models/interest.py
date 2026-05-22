"""Справочник интересов и связка «пользователь ↔ интерес»."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


# Ассоциативная таблица «пользователь ↔ интерес».
# Это чистая связь многие-ко-многим без дополнительных полей,
# поэтому описываем её как Table, а не как модель-класс (так короче и идиоматичнее).
user_interests = Table(
    "user_interests",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("interest_id", ForeignKey("interests.id", ondelete="CASCADE"), primary_key=True),
)


class Interest(Base):
    """
    Справочник интересов.

    Фиксированный список, заполняется заранее (не свободный ввод пользователя).
    Это принципиально для мэтчинга: подбор сравнивает одинаковые interest_id,
    а свободный текст («авто» / «автомобили» / «cars») сломал бы сравнение.
    """

    __tablename__ = "interests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    users: Mapped[list[User]] = relationship(
        secondary=user_interests, back_populates="interests"
    )
