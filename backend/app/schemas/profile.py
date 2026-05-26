"""
Схемы профиля.

ProfileOwnResponse   — полные данные владельцу (имя, возраст, город из User +
                       пол, гео, фото из Profile).
ProfilePublicResponse — публичная карточка другим пользователям
                       (без telegram_id, без точных координат).
ProfileUpdateRequest  — PATCH: только поля из таблицы profiles.
                        Поля User (name, age, about, city) меняются через бот.
"""

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.profile import Gender


class ProfileInterest(BaseModel):
    """Карточка интереса в составе профиля (id + название)."""
    id: int
    name: str


class ProfileUpdateRequest(BaseModel):
    """
    PATCH профиля. Все поля опциональны.

    Часть полей живёт на User (about, interests) — исторически их меняли
    через Telegram-бот. Mini App теперь тоже может их редактировать
    (экран «Профиль» в Tab Bar), поэтому добавлены здесь.
    """
    display_name: str | None = None
    gender: Gender | None = None
    latitude: float | None = None
    longitude: float | None = None
    extra_photos_urls: list[str] | None = None
    is_visible: bool | None = None
    # Поля User, редактируемые через Mini App:
    # about — текст «о себе» (Text NOT NULL в БД, пустую строку отвергаем).
    about: str | None = None
    # interest_ids — полная замена списка интересов (как при регистрации).
    # None → не меняем; [] → очистить все интересы; [1,2,3] → выставить эти.
    interest_ids: list[int] | None = None

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Минимум 2 символа")
        if len(v) > 64:
            raise ValueError("Максимум 64 символа")
        return v

    @field_validator("about")
    @classmethod
    def validate_about(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        # about — NOT NULL в БД. Пустую строку трактуем как «не передано»
        # (PATCH: не редактируем поле), а не как валидное значение.
        if len(v) < 1:
            return None
        if len(v) > 2000:
            raise ValueError("О себе — максимум 2000 символов")
        return v

    @field_validator("extra_photos_urls")
    @classmethod
    def validate_photos(cls, v: list[str] | None) -> list[str] | None:
        if v is not None and len(v) > 5:
            raise ValueError("Максимум 5 дополнительных фото")
        return v

    @model_validator(mode="after")
    def validate_geo(self) -> "ProfileUpdateRequest":
        lat, lon = self.latitude, self.longitude
        if (lat is None) != (lon is None):
            raise ValueError("latitude и longitude передаются только вместе")
        if lat is not None and not (-90 <= lat <= 90):
            raise ValueError("latitude должен быть от -90 до 90")
        if lon is not None and not (-180 <= lon <= 180):
            raise ValueError("longitude должен быть от -180 до 180")
        return self


class ProfileOwnResponse(BaseModel):
    """
    Полный профиль — только для самого пользователя.

    Объединяет данные из User (name, age, about, photo_file_id, city)
    и Profile (display_name, gender, geo, extra_photos, is_visible).
    """
    # Из User
    user_id: int
    name: str
    age: int
    about: str
    photo_file_id: str   # Telegram file_id первого фото (из регистрации через бот)
    city: str
    # Из Profile
    display_name: str | None
    gender: Gender | None
    extra_photos: list[str]
    is_visible: bool
    # Координаты — только себе (другим округляем)
    latitude: float | None
    longitude: float | None
    # Интересы пользователя (id + название). Заполняются сервисом из User.interests.
    interests: list[ProfileInterest] = []


class ProfilePublicResponse(BaseModel):
    """
    Публичная карточка — для показа другим пользователям в ленте.
    Без telegram_id, без точных координат.
    """
    user_id: int
    name: str
    age: int
    about: str
    city: str
    photo_file_id: str
    display_name: str | None
    gender: Gender | None
    extra_photos: list[str]
