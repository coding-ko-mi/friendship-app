"""QuestionnaireRepository — запросы к таблице questionnaires."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.questionnaire import Questionnaire


class QuestionnaireRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_user_id(self, user_id: int) -> Questionnaire | None:
        result = await self.db.execute(
            select(Questionnaire).where(Questionnaire.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create(self, user_id: int) -> Questionnaire:
        q = Questionnaire(user_id=user_id)
        self.db.add(q)
        await self.db.flush()
        await self.db.refresh(q)
        return q

    async def update(self, q: Questionnaire, data: dict) -> Questionnaire:
        for field, value in data.items():
            setattr(q, field, value)
        await self.db.flush()
        await self.db.refresh(q)
        return q
