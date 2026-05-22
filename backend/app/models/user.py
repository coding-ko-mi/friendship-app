"""Модель пользователя (анкета)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.interest import user_interests

if TYPE_CHECKING:
    # Импорт только для подсказок типов — не выполняется в рантайме,
    # поэтому не создаёт циклических импортов между моделями.
    from app.models.achievement import UserAchievement
    from app.models.group import GroupMember
    from app.models.interest import Interest


class User(Base, TimestampMixin):
    """Пользователь приложения и его анкета."""

    __tablename__ = "users"
    __table_args__ = (
        # 18 — минимальный возраст платформы (старт ориентирован на 18–40).
        # Верхняя граница 100 — защита от опечаток, а не продуктовое ограничение.
        CheckConstraint("age >= 18 AND age <= 100", name="ck_user_age_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # telegram_id — числовой ID пользователя из Telegram, по нему авторизуемся.
    # BigInteger: современные Telegram-ID выходят за диапазон 32-битного int.
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    about: Mapped[str] = mapped_column(Text, nullable=False)
    # file_id фото из Telegram. Пользователь присылает фото вручную при регистрации
    # (аватар Telegram не используется). Сам файл не храним — только ссылку Telegram.
    photo_file_id: Mapped[str] = mapped_column(String(256), nullable=False)
    city: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # для гео-подбора
    is_banned: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # --- Связи ---
    # Интересы (многие-ко-многим через таблицу-связку user_interests).
    # Здесь у связки нет доп. полей, поэтому используем secondary, а не модель-класс.
    interests: Mapped[list[Interest]] = relationship(
        secondary=user_interests, back_populates="users"
    )
    # Членства в компаниях. У связки есть поле joined_at, поэтому это
    # ассоциативный объект GroupMember (модель-класс), а не secondary.
    group_memberships: Mapped[list[GroupMember]] = relationship(
        back_populates="user"
    )
    # Полученные достижения (ассоциативный объект UserAchievement, поле earned_at).
    achievement_links: Mapped[list[UserAchievement]] = relationship(
        back_populates="user"
    )
