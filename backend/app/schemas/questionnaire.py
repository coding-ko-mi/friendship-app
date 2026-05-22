"""Схемы анкеты для мэтчинга."""

from pydantic import BaseModel, Field, model_validator

from app.models.questionnaire import Frequency, LookingFor

# Поля, учитываемые при расчёте % заполненности
_COMPLETION_FIELDS = [
    "looking_for", "smoking", "alcohol", "sport",
    "partner_age_min", "partner_age_max", "partner_max_distance_km",
]


class QuestionnaireUpdateRequest(BaseModel):
    """PATCH-обновление анкеты. Все поля опциональны."""
    looking_for: LookingFor | None = None
    smoking: Frequency | None = None
    alcohol: Frequency | None = None
    sport: Frequency | None = None
    partner_age_min: int | None = Field(None, ge=18, le=80)
    partner_age_max: int | None = Field(None, ge=18, le=80)
    partner_max_distance_km: int | None = Field(None, ge=1, le=500)

    @model_validator(mode="after")
    def validate_age_range(self) -> "QuestionnaireUpdateRequest":
        mn, mx = self.partner_age_min, self.partner_age_max
        if mn is not None and mx is not None and mn > mx:
            raise ValueError(
                f"partner_age_min ({mn}) не может быть больше partner_age_max ({mx})"
            )
        return self


class QuestionnaireResponse(BaseModel):
    """Текущее состояние анкеты + % заполненности."""
    user_id: int
    looking_for: LookingFor | None
    smoking: Frequency | None
    alcohol: Frequency | None
    sport: Frequency | None
    partner_age_min: int | None
    partner_age_max: int | None
    partner_max_distance_km: int | None
    # Показываем пользователю прогресс — мотивирует заполнить анкету
    completion_percent: int
