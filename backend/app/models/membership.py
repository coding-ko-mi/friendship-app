"""
Заявки на изменение состава компании и голоса по ним (сценарий Б).

Покрывает три случая одной таблицей: вступление одиночки (join),
приглашение одиночки компанией (invite) и слияние компаний (merge).
Все три проходят единый путь: заявка -> голосование -> результат.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import RequestStatus, RequestType

if TYPE_CHECKING:
    from app.models.group import Group
    from app.models.user import User


class MembershipRequest(Base, TimestampMixin):
    """
    Заявка на изменение состава компании. Тип задаётся полем type:

      join   — одиночка просится в компанию    (заполнен subject_user_id)
      invite — компания зовёт одиночку         (заполнен subject_user_id)
      merge  — компания сливается с компанией  (заполнен subject_group_id)

    Во всех случаях target_group_id — компания, чьи участники голосуют по заявке.
    Субъект — это «кого/что добавляем»: либо одиночка, либо присоединяемая компания.
    """

    __tablename__ = "membership_requests"
    __table_args__ = (
        # Ровно одно из subject_user_id / subject_group_id должно быть заполнено:
        # субъект заявки — это либо человек, либо компания, но не оба и не пусто.
        CheckConstraint(
            "(CASE WHEN subject_user_id IS NULL THEN 0 ELSE 1 END) "
            "+ (CASE WHEN subject_group_id IS NULL THEN 0 ELSE 1 END) = 1",
            name="ck_request_exactly_one_subject",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # native_enum=False: храним значение как VARCHAR + CHECK, а не как нативный
    # PostgreSQL ENUM. Так проще менять список значений в будущих миграциях.
    type: Mapped[RequestType] = mapped_column(
        Enum(RequestType, native_enum=False, length=16), nullable=False
    )
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus, native_enum=False, length=16),
        nullable=False,
        default=RequestStatus.PENDING,
        server_default=RequestStatus.PENDING.value,
    )

    # Субъект-одиночка ИЛИ субъект-компания (ровно один — см. CHECK выше).
    subject_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    subject_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # Компания, чьи участники голосуют.
    target_group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Два FK на groups (subject_group_id и target_group_id) -> явный foreign_keys.
    subject_user: Mapped[User | None] = relationship(foreign_keys=[subject_user_id])
    subject_group: Mapped[Group | None] = relationship(foreign_keys=[subject_group_id])
    target_group: Mapped[Group] = relationship(foreign_keys=[target_group_id])
    votes: Mapped[list[Vote]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )


class Vote(Base, TimestampMixin):
    """
    Голос участника компании по заявке.

    Анонимность голосования: voter_id хранится в БД — он нужен, чтобы
    (а) посчитать порог 75% и (б) запретить голосовать дважды.
    Но API НИКОГДА не отдаёт voter_id наружу. Анонимность реализуется
    на уровне приложения («храним, но не показываем»), а не отсутствием данных.
    """

    __tablename__ = "votes"
    __table_args__ = (
        # Один участник — один голос на конкретную заявку.
        UniqueConstraint("request_id", "voter_id", name="uq_vote_once_per_request"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("membership_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    voter_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    value: Mapped[bool] = mapped_column(Boolean, nullable=False)  # True = «за», False = «против»

    request: Mapped[MembershipRequest] = relationship(back_populates="votes")
    voter: Mapped[User] = relationship(foreign_keys=[voter_id])
