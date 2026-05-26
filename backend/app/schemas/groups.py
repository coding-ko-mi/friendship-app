"""
Pydantic-схемы модуля «Компании + голосование» (сценарий Б).

Схемы описывают форму данных на границе API (что приходит, что уходит).
Бизнес-логика и ORM-модели сюда не лезут — только сериализация/валидация.

Зеркалит стиль app/schemas/matching.py: from_attributes для сборки из ORM,
Field с дефолтами, без бизнес-правил внутри схем.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RequestStatus, RequestType


# ===================================================================== #
#  СОЗДАНИЕ КОМПАНИИ                                                     #
# ===================================================================== #
class GroupCreate(BaseModel):
    """
    Запрос на создание компании (Вариант 2: из подтверждённого мэтча).

    Компания рождается из двух уже сматчившихся одиночек: инициатор
    (текущий пользователь) + партнёр по мэтчу. Поэтому на вход — id мэтча,
    а не список пользователей: так сервис проверит, что мэтч реальный и
    текущий пользователь действительно его участник.
    """

    name: str = Field(min_length=1, max_length=128, description="Название компании")
    match_id: int = Field(description="id подтверждённого мэтча, из которого рождается компания")


# ===================================================================== #
#  ПРЕДСТАВЛЕНИЕ КОМПАНИИ И УЧАСТНИКОВ                                   #
# ===================================================================== #
class GroupMemberCard(BaseModel):
    """
    Карточка участника компании (публичные данные для отображения состава).

    Чувствительного (telegram_id) здесь нет намеренно, как и в CandidateCard.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    age: int
    photo_file_id: str
    city: str


class GroupCard(BaseModel):
    """Базовая информация о компании + её состав."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    # telegram_chat_id может быть None: чат компании создаётся модулем «Бот»
    # отдельно, компания существует в БД до привязки чата.
    telegram_chat_id: int | None = None
    members: list[GroupMemberCard] = Field(default_factory=list)
    member_count: int = 0


class GroupSummary(BaseModel):
    """
    Лёгкая карточка компании для списков (без подгрузки состава).

    Используется на экране «Матчи → Компании»: там показываем только название
    и число участников. Подробный состав покажет GroupCard при открытии.
    """

    id: int
    name: str
    member_count: int


# ===================================================================== #
#  ЗАЯВКИ НА ИЗМЕНЕНИЕ СОСТАВА                                           #
# ===================================================================== #
class RequestCreate(BaseModel):
    """
    Запрос на создание заявки (join / invite / merge).

    Тип заявки + субъект «кого/что добавляем». Заполняется ровно одно из
    subject_user_id / subject_group_id — это same CHECK, что в модели
    MembershipRequest. Валидацию «ровно один субъект» делает сервис
    (даёт понятную доменную ошибку до удара в БД-CHECK).

      join   → subject_user_id  (одиночка просится в target-компанию)
      invite → subject_user_id  (target-компания зовёт одиночку)
      merge  → subject_group_id (subject-компания вливается в target-компанию)
    """

    type: RequestType
    subject_user_id: int | None = Field(
        default=None, description="id одиночки (для join/invite)"
    )
    subject_group_id: int | None = Field(
        default=None, description="id присоединяемой компании (для merge)"
    )


class VoteProgress(BaseModel):
    """
    Прогресс голосования по одной компании.

    Для merge таких блоков два (target и subject голосуют раздельно),
    для join/invite — один (голосует только target-компания).
    """

    group_id: int
    members_total: int  # сколько участников в компании (= сколько вправе голосовать)
    votes_yes: int      # голосов «за»
    votes_no: int       # голосов «против»
    threshold: int      # сколько «за» нужно для прохождения (75%, округление вверх)
    passed: bool        # достигнут ли порог в этой компании


class RequestCard(BaseModel):
    """
    Карточка заявки + текущий статус голосования.

    progress — список прогрессов по компаниям-голосующим: один элемент для
    join/invite, два для merge. Это даёт фронту единый формат для всех типов.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    type: RequestType
    status: RequestStatus
    subject_user_id: int | None = None
    subject_group_id: int | None = None
    target_group_id: int
    created_at: datetime
    progress: list[VoteProgress] = Field(default_factory=list)


# ===================================================================== #
#  РЕЗУЛЬТАТЫ ДЕЙСТВИЙ                                                   #
# ===================================================================== #
class VoteResult(BaseModel):
    """
    Результат поданного голоса.

    finalized=True означает, что этот голос закрыл голосование (порог достигнут
    во всех нужных компаниях ИЛИ стало математически невозможно его достичь).
    status — итоговый статус заявки после голоса (VOTING / ACCEPTED / REJECTED).
    """

    request_id: int
    status: RequestStatus
    finalized: bool
    # Заполняется, только когда заявка принята и кто-то реально добавлен в компанию.
    added_user_id: int | None = None
