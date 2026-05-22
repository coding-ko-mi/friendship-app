"""
Модель Profile — дополнительные публичные данные пользователя.

Существующая модель User уже содержит:
    name, age, about, photo_file_id, city, is_banned

Profile добавляет поля, которых нет в User:
    display_name  — необязательный псевдоним
    gender        — пол (не влияет на мэтчинг в MVP)
    latitude/longitude — точные координаты (User имеет только city-строку)
    extra_photos_urls — дополнительные фото (User хранит один photo_file_id)
    is_visible    — флаг видимости в ленте поиска

Связь: один User → один Profile (One-to-One).
FK → users.id (Integer, совпадает с типом PK существующей таблицы users).
"""

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Gender(str, enum.Enum):
    """
    Пол пользователя. str-миксин: можно сравнивать как строку.
    В MVP не влияет на алгоритм мэтчинга — только хранится и показывается.
    """
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class Profile(Base, TimestampMixin):
    """Таблица: profiles"""

    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # FK на существующую таблицу users (Integer PK, не BigInteger)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # Необязательный псевдоним, может отличаться от User.name
    display_name: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Пол — обязательно при заполнении, но null сразу после регистрации (бот спрашивает постепенно)
    gender: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Точные координаты для расчёта расстояния.
    # В публичных ответах округляем до ~1 км, точные значения наружу не отдаём.
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)

    # Дополнительные фото (сверх photo_file_id из User).
    # Формат: "url1|url2|url3" — простое решение для MVP.
    # При появлении загрузки файлов мигрируем на таблицу photos.
    extra_photos_urls: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Видимость в ленте поиска. False = «пауза» без удаления аккаунта.
    is_visible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    def get_extra_photos(self) -> list[str]:
        if not self.extra_photos_urls:
            return []
        return [u for u in self.extra_photos_urls.split("|") if u]

    def set_extra_photos(self, urls: list[str]) -> None:
        self.extra_photos_urls = "|".join(u.strip() for u in urls if u.strip())

    def __repr__(self) -> str:
        return f"<Profile user_id={self.user_id} gender={self.gender}>"
