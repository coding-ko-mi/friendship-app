"""Базовый класс ORM и общие миксины."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    Базовый класс для всех ORM-моделей.

    Все таблицы наследуются от него. SQLAlchemy собирает их схему
    в Base.metadata — именно её Alembic использует для генерации миграций.
    """


class TimestampMixin:
    """
    Миксин с полем created_at.

    Подмешивается в модели, которым нужна отметка времени создания.
    server_default=func.now() — время проставляет сама БД при вставке строки,
    а не Python, поэтому оно всегда консистентно и не зависит от часов сервера приложения.
    timezone=True — храним время с таймзоной (timestamptz в PostgreSQL).
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
