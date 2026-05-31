"""Модели компании (группы) и её участников."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class Group(Base, TimestampMixin):
    """Компания — группа друзей, собранная пользователями."""

    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # ID Telegram-чата компании. В модели «Чатинг» (вариант Б) это ID общей
    # Hub-супергруппы — ОДИНАКОВЫЙ для всех компаний, поэтому unique УБРАН.
    # Связку «компания → её тред» задаёт пара (telegram_chat_id, message_thread_id).
    # nullable: компания существует в БД до того, как бот создаст ей топик.
    telegram_chat_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    # ID топика (forum thread) этой компании внутри Hub-супергруппы.
    # Бот заполняет его после createForumTopic. Сообщения компании шлются с
    # message_thread_id=<это значение>. nullable по той же причине, что выше.
    message_thread_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    # Участники компании. delete-orphan: при удалении компании её членства тоже удаляются.
    members: Mapped[list[GroupMember]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )


class GroupMember(Base):
    """
    Участник компании. Ассоциативный объект «пользователь ↔ компания».

    Это модель-класс (а не Table), потому что у связки есть доп. поле joined_at.
    Один пользователь может состоять в нескольких компаниях одновременно,
    поэтому первичный ключ — пара (user_id, group_id).

    Роли участников на MVP нет: «основатель» — это достижение (UserAchievement),
    а не роль в группе. Иначе слияние компаний (merge) ломало бы концепцию
    единственного основателя.
    """

    __tablename__ = "group_members"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="group_memberships")
    group: Mapped[Group] = relationship(back_populates="members")
