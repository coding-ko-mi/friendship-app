"""
Pydantic-схемы модуля «Мэтчинг».

Схемы описывают форму данных на границе API (что приходит и что уходит).
Бизнес-логика и ORM-модели сюда не лезут — только сериализация.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CandidateCard(BaseModel):
    """
    Карточка кандидата в ленте свайпов.

    Это публичные данные другого пользователя — то, что видно при листании.
    Чувствительного (telegram_id и пр.) здесь нет намеренно.
    """

    # from_attributes=True: разрешаем собирать схему прямо из ORM-объекта User
    # (model_validate(user)), без ручного перекладывания полей.
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    age: int
    about: str
    photo_file_id: str
    city: str
    # Названия общих с текущим пользователем интересов — заполняются сервисом,
    # не берутся из ORM напрямую. Помогают фронту показать «что вас объединяет».
    shared_interests: list[str] = Field(default_factory=list)
    # Сколько интересов совпало — то самое число, по которому ранжируется лента.
    shared_count: int = 0


class DiscoveryFeed(BaseModel):
    """Страница ленты: список карточек + курсор для подгрузки следующей порции."""

    candidates: list[CandidateCard]
    # Курсор для пагинации: id последнего показанного кандидата.
    # Фронт передаёт его в следующий запрос, чтобы не получить дубли.
    # None — если кандидатов больше нет.
    next_cursor: int | None = None


class LikeResult(BaseModel):
    """
    Результат постановки лайка.

    is_mutual=True означает, что встречный лайк уже был и создан Match.
    match_id заполняется только в этом случае. Сам пуш-уведомление о мэтче
    отправляет модуль «Бот» (aiogram) — здесь мы лишь сообщаем факт наружу.
    """

    is_mutual: bool
    match_id: int | None = None


class SkipResult(BaseModel):
    """Результат skip: подтверждение, что кандидат убран из ленты на время TTL."""

    skipped_user_id: int


# ===================================================================== #
#  МЭТЧИ (список взаимных лайков)                                        #
# ===================================================================== #
class MatchCard(BaseModel):
    """
    Карточка одного мэтча для экрана «Матчи».

    user_id — id СОБЕСЕДНИКА (второго участника пары, не текущего).
    matched_at — когда был создан мэтч (для сортировки/отображения).
    """

    match_id: int
    user_id: int
    name: str
    age: int
    photo_file_id: str
    matched_at: datetime


# ===================================================================== #
#  ИСТОРИЯ ЛАЙКОВ                                                        #
# ===================================================================== #
class LikedUserCard(BaseModel):
    """
    Карточка одного лайкнутого пользователя для экрана «История».

    Скипы храним в Redis (TTL) — здесь только лайки из таблицы likes.
    """

    target_user_id: int
    name: str
    age: int
    photo_file_id: str
    liked_at: datetime
