"""
Модель Questionnaire — анкета для мэтчинга.

Адаптирована под friendship-приложение:
- Цель: ищу компанию / ищу друзей 1-на-1 / и то, и другое
  (НЕ «серьёзные отношения / casual» — это дейтинговые категории)
- Интересы НЕ дублируются здесь — они уже хранятся в таблице user_interests
  через связь Many-to-Many (Interest ↔ User). Мэтчинг по интересам
  использует существующую схему.
- Образ жизни: smoking, alcohol, sport (Frequency)
- Предпочтения: возраст партнёра, максимальное расстояние

FK → users.id (Integer, совпадает с типом PK существующей таблицы users).
"""

import enum

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class LookingFor(str, enum.Enum):
    """Что ищет пользователь в приложении."""
    GROUP = "group"        # ищу компанию / группу
    FRIENDS = "friends"    # ищу друзей 1-на-1
    BOTH = "both"          # и то, и другое


class Frequency(str, enum.Enum):
    """Частота привычки (курение, алкоголь, спорт)."""
    NEVER = "never"
    SOMETIMES = "sometimes"
    OFTEN = "often"


class Questionnaire(Base, TimestampMixin):
    """Таблица: questionnaires"""

    __tablename__ = "questionnaires"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # --- Цель ---
    # Что ищет пользователь: группу, друзей 1-на-1, или оба варианта.
    # String вместо Enum-типа Postgres: легко добавлять значения без DDL-миграции.
    looking_for: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # --- Образ жизни ---
    smoking: Mapped[str | None] = mapped_column(String(20), nullable=True)
    alcohol: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sport: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # --- Предпочтения партнёра ---
    partner_age_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    partner_age_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # None = без ограничения по расстоянию (весь город / вся страна)
    partner_max_distance_km: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return f"<Questionnaire user_id={self.user_id} looking_for={self.looking_for}>"
