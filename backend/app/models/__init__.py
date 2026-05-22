"""
Единая точка импорта всех моделей.

Импортируя app.models, регистрируем все таблицы в Base.metadata.
Это нужно, чтобы Alembic (autogenerate) и create_all «видели» полную схему.
"""

# --- Существующие модели (не изменять) ---
from app.models.achievement import Achievement, UserAchievement
from app.models.base import Base
from app.models.group import Group, GroupMember
from app.models.interest import Interest, user_interests
from app.models.matching import Like, Match
from app.models.membership import MembershipRequest, Vote
from app.models.user import User

# --- Новые модели (добавлены в модуле «Бэкенд: ядро») ---
from app.models.profile import Profile, Gender
from app.models.questionnaire import Questionnaire, LookingFor, Frequency

__all__ = [
    "Base", "User", "Interest", "user_interests",
    "Group", "GroupMember", "Like", "Match",
    "MembershipRequest", "Vote", "Achievement", "UserAchievement",
    "Profile", "Gender", "Questionnaire", "LookingFor", "Frequency",
]
