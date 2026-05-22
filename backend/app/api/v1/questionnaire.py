"""Questionnaire router."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_session
from app.models.user import User
from app.schemas.questionnaire import QuestionnaireResponse, QuestionnaireUpdateRequest
from app.services.questionnaire_service import QuestionnaireService

router = APIRouter(tags=["questionnaire"])


def _get_service(db: AsyncSession = Depends(get_session)) -> QuestionnaireService:
    return QuestionnaireService(db)


@router.get("/me/questionnaire", response_model=QuestionnaireResponse)
async def get_my_questionnaire(
    current_user: User = Depends(get_current_user),
    service: QuestionnaireService = Depends(_get_service),
) -> QuestionnaireResponse:
    """Получить свою анкету. completion_percent показывает % заполненности."""
    return await service.get_my_questionnaire(current_user)


@router.patch("/me/questionnaire", response_model=QuestionnaireResponse)
async def update_my_questionnaire(
    body: QuestionnaireUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: QuestionnaireService = Depends(_get_service),
) -> QuestionnaireResponse:
    """
    Обновить анкету. Каждый блок можно менять независимо:
    {"looking_for": "group"}         — только цель
    {"smoking": "never"}             — только образ жизни
    {"partner_age_min": 22}          — только предпочтения
    """
    return await service.update_my_questionnaire(current_user, body)
