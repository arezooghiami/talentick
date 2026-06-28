"""
Talentick — Onboarding Models
================================
جداول: onboarding_programs, program_steps,
        user_program_enrollments, user_step_progress

هر برنامه آشنایی (Learning Journey) شامل چندین مرحله است.
هر مرحله می‌تواند: محتوا، آزمون، یا آپلود مدرک باشد.
آزمون در هر مرحله کاملاً اختیاری است.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

# نوع مرحله
STEP_TYPES = ("content", "quiz", "document_upload", "custom")

# وضعیت پیشرفت کاربر
STEP_STATUSES = ("not_started", "in_progress", "completed", "skipped")


class OnboardingProgram(UUIDMixin, TimestampMixin, Base):
    """
    برنامه آشنایی سازمانی — Learning Journey.

    مثال:
    - برنامه آشنایی کارمندان جدید (برای همه)
    - برنامه آشنایی مدیران (فقط manager)
    - برنامه آشنایی تیم فروش (فقط dept فروش)
    """

    __tablename__ = "onboarding_programs"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(500), nullable=False,
        comment="نام برنامه — مثال: برنامه آشنایی کارمندان جدید"
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # هدف‌گذاری — چه کسی این برنامه را می‌بیند
    target_roles: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list,
        comment="نقش‌های هدف — خالی یعنی همه"
    )
    target_dept_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        comment="واحد هدف — null یعنی همه واحدها"
    )

    # پیش‌فرض بودن — اگر true هر کارمند جدید خودکار ثبت‌نام می‌شود
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="ثبت‌نام خودکار برای کارمندان جدید"
    )

    # مهلت تکمیل به روز (از زمان ثبت‌نام)
    deadline_days: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="مهلت تکمیل — null یعنی بدون مهلت"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ─── Relationships ────────────────────────────────────────────────────
    steps: Mapped[list["ProgramStep"]] = relationship(
        back_populates="program",
        cascade="all, delete-orphan",
        order_by="ProgramStep.order_index",
    )
    enrollments: Mapped[list["UserProgramEnrollment"]] = relationship(
        back_populates="program", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<OnboardingProgram name={self.name!r}>"


class ProgramStep(UUIDMixin, TimestampMixin, Base):
    """
    مرحله‌های یک برنامه آشنایی.

    انواع مرحله:
    - content: مطالعه/تماشای یک محتوا
    - quiz: شرکت در آزمون (اختیاری)
    - document_upload: آپلود مدرک (مثل کارت ملی)
    - custom: توضیح آزاد بدون action
    """

    __tablename__ = "program_steps"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    program_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("onboarding_programs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="content | quiz | document_upload | custom"
    )

    # برای type=content: کدام محتوا
    content_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contents.id", ondelete="SET NULL"),
        nullable=True,
    )
    # برای type=quiz: کدام آزمون (اختیاری است)
    quiz_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("quizzes.id", ondelete="SET NULL"),
        nullable=True,
        comment="آزمون اختیاری — null یعنی آزمون ندارد"
    )

    is_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
        comment="آیا تکمیل این مرحله اجباری است؟"
    )
    order_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    # ─── Relationships ────────────────────────────────────────────────────
    program: Mapped["OnboardingProgram"] = relationship(back_populates="steps")

    def __repr__(self) -> str:
        return f"<ProgramStep type={self.type!r} title={self.title!r}>"


class UserProgramEnrollment(UUIDMixin, TimestampMixin, Base):
    """
    ثبت‌نام کاربر در یک برنامه آشنایی.

    یک کاربر می‌تواند در چندین برنامه ثبت‌نام کند.
    """

    __tablename__ = "user_program_enrollments"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    program_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("onboarding_programs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    enrolled_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="چه کسی ثبت‌نام کرده — null یعنی خودکار"
    )

    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    deadline_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    progress_pct: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    # ─── Relationships ────────────────────────────────────────────────────
    program: Mapped["OnboardingProgram"] = relationship(back_populates="enrollments")
    step_progresses: Mapped[list["UserStepProgress"]] = relationship(
        back_populates="enrollment", cascade="all, delete-orphan"
    )


class UserStepProgress(UUIDMixin, TimestampMixin, Base):
    """
    پیشرفت کاربر در هر مرحله از برنامه.

    status:
    - not_started: هنوز شروع نشده
    - in_progress:  در حال انجام
    - completed:    تکمیل شده
    - skipped:      رد شده (برای مراحل اختیاری)
    """

    __tablename__ = "user_step_progress"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("program_steps.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_program_enrollments.id", ondelete="CASCADE"),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="not_started",
        comment="not_started | in_progress | completed | skipped"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ─── Relationships ────────────────────────────────────────────────────
    enrollment: Mapped["UserProgramEnrollment"] = relationship(
        back_populates="step_progresses"
    )