"""
Pydantic-схемы модуля «Регистрация» (гибрид: фото из бота + анкета из Mini App).

Поток регистрации (Вариант A):
  1. Пользователь жмёт /start в боте → бот просит прислать фото.
  2. Бот кладёт photo_file_id в Redis по ключу pending_photo:{telegram_id}.
  3. Бот открывает Mini App кнопкой.
  4. Mini App собирает остальные поля анкеты и шлёт RegistrationRequest сюда.
  5. API забирает фото из Redis и создаёт User одним INSERT (все поля NOT NULL).

Схемы описывают только форму данных на границе API — без бизнес-логики и ORM.
Зеркалит стиль app/schemas/matching.py и app/schemas/groups.py.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RegistrationRequest(BaseModel):
    """
    Данные анкеты из Mini App (всё, КРОМЕ фото).

    Фото не передаётся здесь: его прислали боту отдельным шагом, и API берёт
    его из Redis по telegram_id текущего пользователя. Так file_id не светится
    в запросах фронта и не зависит от него.

    telegram_id тоже не в теле запроса — он берётся из авторизации (initData),
    чтобы клиент не мог зарегистрировать чужой аккаунт.
    """

    # Ограничения дублируют схему БД (User.name = String(64) и т.п.), чтобы
    # вернуть понятную 422-ошибку на границе, а не ловить отказ БД глубже.
    name: str = Field(min_length=1, max_length=64, description="Имя")
    age: int = Field(ge=18, le=100, description="Возраст (18–100, как CHECK в БД)")
    about: str = Field(min_length=1, max_length=2000, description="Текст «о себе»")
    city: str = Field(min_length=1, max_length=64, description="Город (для гео-подбора)")
    # Интересы — только id из справочника interests (свободный ввод запрещён,
    # иначе сломается мэтчинг по interest_id). Минимум один интерес обязателен:
    # это ключевой элемент анкеты и основа подбора.
    interest_ids: list[int] = Field(
        min_length=1, description="id выбранных интересов из справочника"
    )


class RegistrationResponse(BaseModel):
    """Подтверждение успешной регистрации (минимум для фронта)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    # Фронт после регистрации обычно сразу ведёт пользователя в ленту —
    # отдаём id созданного профиля, остальное он дотянет через /me/profile.
