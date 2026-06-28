"""
Talentick — Models Package
===========================
تمام مدل‌ها اینجا import می‌شوند تا:
1. Alembic autogenerate همه جداول را ببیند
2. SQLAlchemy relationship ها resolve شوند

هر مدل جدید را اینجا اضافه کنید.
"""

from app.models.base import Base  # noqa: F401
from app.models.content import Content, ContentItem, UserContentProgress  # noqa: F401
from app.models.onboarding import (  # noqa: F401
    OnboardingProgram,
    ProgramStep,
    UserProgramEnrollment,
    UserStepProgress,
)
from app.models.organization import Department, Organization, Position  # noqa: F401
from app.models.quiz import Quiz, Question, QuestionOption, QuizAttempt  # noqa: F401
from app.models.user import Invitation, RefreshToken, User  # noqa: F401

__all__ = [
    "Base",
    # Organization
    "Organization",
    "Department",
    "Position",
    # User
    "User",
    "RefreshToken",
    "Invitation",
    # Content
    "Content",
    "ContentItem",
    "UserContentProgress",
    # Onboarding
    "OnboardingProgram",
    "ProgramStep",
    "UserProgramEnrollment",
    "UserStepProgress",
    # Quiz
    "Quiz",
    "Question",
    "QuestionOption",
    "QuizAttempt",
]