"""Справочник интересов — только чтение (для онбординга Mini App)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.interest import Interest


class InterestCard(BaseModel):
    """Карточка интереса для Mini App: только id + name."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


router = APIRouter(prefix="/interests", tags=["interests"])


@router.get("", response_model=list[InterestCard])
async def list_interests(
    session: AsyncSession = Depends(get_session),
) -> list[Interest]:
    """Весь справочник интересов. Без авторизации: данные публичные."""
    result = await session.execute(select(Interest).order_by(Interest.id))
    return list(result.scalars().all())
