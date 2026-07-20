"""
Talentick — Points (Gamification) Models
============================================
جداول: point_rules, points_ledger, point_group_overrides

سیستم امتیاز — برای هر اتفاق تکمیل (آیتم محتوا، کل محتوا، قبولی آزمون،
مرحله‌ی آنبوردینگ، کل برنامه‌ی آنبوردینگ) یک ردیف در points_ledger ثبت
می‌شود. مقدار امتیاز یک سیاست سه‌لایه دارد:

  ۱. مقدار سراسری پیش‌فرض هر نوع اتفاق: point_rules (فقط super_admin)
  ۲. override اختصاصیِ خودِ موجودیت: ستون points_override روی خود
     Quiz/Content/ContentItem/ProgramStep/OnboardingProgram — در فرم
     ساخت/ویرایش همان موجودیت تنظیم می‌شود (نه اینجا).
  ۳. override برای یک گروه کاربر (نقش یا واحد سازمانی): point_group_overrides

قانون تعارض: اگر برای یک اهدای امتیاز، هم override اختصاصیِ موجودیت و
هم override گروهی (نقش/واحد) هم‌زمان صدق کند، مقدار کمتر برنده می‌شود —
یعنی محتاطانه‌ترین سیاست همیشه اعمال می‌شود. اگر هیچ‌کدام صدق نکند،
مقدار پیش‌فرض سراسری (point_rules) استفاده می‌شود.

قانون طلایی idempotency: هر ترکیب (user_id, event_type, reference_id)
حداکثر یک بار امتیاز می‌گیرد — همین «فقط بار اول» را هم برای قبولی
مجدد در یک آزمون تضمین می‌کند (reference_id = quiz_id، نه attempt_id).
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin

EVENT_TYPES = (
    "content_item_completed",
    "content_completed",
    "quiz_passed",
    "onboarding_step_completed",
    "onboarding_program_completed",
)

GROUP_TARGET_TYPES = ("role", "department")


class PointRule(UUIDMixin, TimestampMixin, Base):
    """مقدار امتیاز هر نوع اتفاق — سراسری، فقط super_admin مدیریت می‌کند."""

    __tablename__ = "point_rules"

    event_type: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<PointRule event_type={self.event_type!r} points={self.points}>"


class PointsLedgerEntry(UUIDMixin, Base):
    """
    یک ردیف دفترکل امتیاز — همیشه add-only (هیچ‌وقت update/delete نمی‌شود).

    points مقدار واقعی امتیازِ لحظه‌ی اهدا را ذخیره می‌کند (نه ارجاع زنده
    به PointRule) — تغییر بعدی مقدار قانون توسط super_admin نباید
    تاریخچه‌ی قبلی را عوض کند.
    """

    __tablename__ = "points_ledger"
    __table_args__ = (
        UniqueConstraint("user_id", "event_type", "reference_id", name="uq_points_ledger_event"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    reference_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False,
        comment="شناسه‌ی موجودیت مرتبط — content_item/content/quiz/program_step/onboarding_program",
    )
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<PointsLedgerEntry user={self.user_id} event={self.event_type} points={self.points}>"


class PointGroupOverride(UUIDMixin, TimestampMixin, Base):
    """
    override امتیاز برای یک گروه کاربر (نقش یا واحد سازمانی) — سراسری،
    per event_type، فقط super_admin مدیریت می‌کند. مستقل از
    points_override اختصاصی خود موجودیت (Quiz/Content/...).
    """

    __tablename__ = "point_group_overrides"
    __table_args__ = (
        UniqueConstraint("event_type", "target_type", "target_value", name="uq_point_group_override"),
    )

    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="role | department")
    target_value: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="نام نقش برای role — UUID واحد سازمانی برای department",
    )
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<PointGroupOverride event={self.event_type} {self.target_type}={self.target_value} points={self.points}>"
