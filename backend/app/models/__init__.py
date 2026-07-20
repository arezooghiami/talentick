"""
Talentick — Models Package
===========================
تمام مدل‌ها اینجا import می‌شوند تا:
1. Alembic autogenerate همه جداول را ببیند
2. SQLAlchemy relationship ها resolve شوند

هر مدل جدید را اینجا اضافه کنید.
"""

from app.models.announcement import Announcement, AnnouncementTarget  # noqa: F401
from app.models.base import Base  # noqa: F401
from app.models.content import (  # noqa: F401
    Content,
    ContentItem,
    ContentTarget,
    UserContentProgress,
)
from app.models.document import Document, DocumentCategory, DocumentTarget  # noqa: F401
from app.models.onboarding import (  # noqa: F401
    OnboardingProgram,
    ProgramStep,
    UserProgramEnrollment,
    UserStepProgress,
)
from app.models.organization import Department, Organization, Position  # noqa: F401
from app.models.points import PointGroupOverride, PointRule, PointsLedgerEntry  # noqa: F401
from app.models.quiz import Quiz, Question, QuestionOption, QuizAttempt  # noqa: F401
from app.models.ticket import (  # noqa: F401
    Ticket,
    TicketAccessGrant,
    TicketCategory,
    TicketMessage,
)
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
    "ContentTarget",
    "UserContentProgress",
    # Document Library
    "Document",
    "DocumentCategory",
    "DocumentTarget",
    # Announcements
    "Announcement",
    "AnnouncementTarget",
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
    # Ticketing
    "Ticket",
    "TicketMessage",
    "TicketCategory",
    "TicketAccessGrant",
    # Gamification
    "PointRule",
    "PointsLedgerEntry",
    "PointGroupOverride",
]