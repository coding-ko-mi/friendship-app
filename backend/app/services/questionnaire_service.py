"""
QuestionnaireService — работа с анкетой пользователя.

Интересы НЕ входят в анкету — они управляются через существующую
таблицу user_interests (связь User ↔ Interest).
Анкета содержит: цель, образ жизни, предпочтения партнёра.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.questionnaire import Questionnaire
from app.models.user import User
from app.repositories.questionnaire_repository import QuestionnaireRepository
from app.schemas.questionnaire import (
    QuestionnaireResponse,
    QuestionnaireUpdateRequest,
    _COMPLETION_FIELDS,
)


class QuestionnaireService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = QuestionnaireRepository(db)

    async def get_my_questionnaire(self, current_user: User) -> QuestionnaireResponse:
        q = await self._get_or_create(current_user.id)
        return self._build_response(q)

    async def update_my_questionnaire(
        self, current_user: User, data: QuestionnaireUpdateRequest
    ) -> QuestionnaireResponse:
        q = await self._get_or_create(current_user.id)

        update_data: dict = {}
        # Enum-поля — сохраняем как строку
        if data.looking_for is not None:
            update_data["looking_for"] = data.looking_for.value
        if data.smoking is not None:
            update_data["smoking"] = data.smoking.value
        if data.alcohol is not None:
            update_data["alcohol"] = data.alcohol.value
        if data.sport is not None:
            update_data["sport"] = data.sport.value
        if data.partner_age_min is not None:
            update_data["partner_age_min"] = data.partner_age_min
        if data.partner_age_max is not None:
            update_data["partner_age_max"] = data.partner_age_max
        if data.partner_max_distance_km is not None:
            update_data["partner_max_distance_km"] = data.partner_max_distance_km

        if update_data:
            q = await self.repo.update(q, update_data)

        await self.db.commit()
        return self._build_response(q)

    async def create_for_user(self, user_id: int) -> Questionnaire:
        """Вызывается при первом входе через Mini App."""
        return await self.repo.create(user_id)

    # ------------------------------------------------------------------

    async def _get_or_create(self, user_id: int) -> Questionnaire:
        q = await self.repo.get_by_user_id(user_id)
        if q is None:
            q = await self.repo.create(user_id)
            await self.db.commit()
        return q

    def _build_response(self, q: Questionnaire) -> QuestionnaireResponse:
        return QuestionnaireResponse(
            user_id=q.user_id,
            looking_for=q.looking_for,
            smoking=q.smoking,
            alcohol=q.alcohol,
            sport=q.sport,
            partner_age_min=q.partner_age_min,
            partner_age_max=q.partner_age_max,
            partner_max_distance_km=q.partner_max_distance_km,
            completion_percent=self._calc_completion(q),
        )

    @staticmethod
    def _calc_completion(q: Questionnaire) -> int:
        filled = sum(
            1 for f in _COMPLETION_FIELDS
            if getattr(q, f) not in (None, "")
        )
        return round(filled / len(_COMPLETION_FIELDS) * 100)
