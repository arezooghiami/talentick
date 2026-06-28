"""
Talentick — Quiz Models
========================
جداول: quizzes, questions, question_options, quiz_attempts

این ماژول کاملاً مستقل است — می‌تواند در:
  - ContentItem (درس آزمون)
  - ProgramStep (مرحله آزمون)
  - یا مستقل (آزمون ورودی)
استفاده شود.

قانون مهم: هر attempt ثبت می‌شود — هرگز update نمی‌شود.
تاریخچه کامل پاسخ‌ها در answers (JSONB) ذخیره می‌شود.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

# انواع سوال
QUESTION_TYPES = ("single_choice", "multi_choice", "true_false", "short_text")


class Quiz(UUIDMixin, TimestampMixin, Base):
    """
    آزمون — می‌تواند به یک محتوا، مرحله onboarding، یا آزمون مستقل باشد.

    is_onboarding=True برای آزمون ورودی استفاده می‌شود.
    """

    __tablename__ = "quizzes"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # نمره قبولی (0-100)
    pass_score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=70,
        comment="نمره قبولی — درصد از 100"
    )

    # محدودیت زمان به دقیقه — null یعنی بدون محدودیت
    time_limit_min: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="مهلت پاسخگویی به دقیقه — null یعنی نامحدود"
    )

    # آیا سوالات به صورت تصادفی نمایش داده شوند؟
    shuffle_questions: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    shuffle_options: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # آزمون ورودی — برای onboarding
    is_onboarding: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="آزمون ورودی سازمان"
    )

    # حداکثر تعداد دفعات شرکت — null یعنی نامحدود
    max_attempts: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="null یعنی می‌توان بارها شرکت کرد"
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ─── Relationships ────────────────────────────────────────────────────
    questions: Mapped[list["Question"]] = relationship(
        back_populates="quiz",
        cascade="all, delete-orphan",
        order_by="Question.order_index",
    )
    attempts: Mapped[list["QuizAttempt"]] = relationship(
        back_populates="quiz", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Quiz title={self.title!r} pass_score={self.pass_score}>"


class Question(UUIDMixin, TimestampMixin, Base):
    """
    سوال آزمون.

    انواع:
    - single_choice:  یک گزینه درست
    - multi_choice:   چند گزینه می‌توان انتخاب کرد
    - true_false:     درست/غلط
    - short_text:     پاسخ متنی (نمره‌دهی دستی)
    """

    __tablename__ = "questions"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    quiz_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("quizzes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    body: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="متن سوال"
    )
    type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="single_choice | multi_choice | true_false | short_text"
    )

    # توضیح پاسخ صحیح (نشان داده می‌شود بعد از پاسخ)
    explanation: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="توضیح پاسخ درست — نشان داده می‌شود بعد از ارسال"
    )

    # امتیاز این سوال
    score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1,
        comment="امتیاز این سوال"
    )
    order_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    # ─── Relationships ────────────────────────────────────────────────────
    quiz: Mapped["Quiz"] = relationship(back_populates="questions")
    options: Mapped[list["QuestionOption"]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="QuestionOption.order_index",
    )

    def __repr__(self) -> str:
        return f"<Question type={self.type!r} body={self.body[:50]!r}>"


class QuestionOption(UUIDMixin, Base):
    """
    گزینه‌های یک سوال چندگزینه‌ای.

    is_correct مشخص می‌کند کدام گزینه درست است.
    برای single_choice: فقط یک is_correct=True
    برای multi_choice: می‌تواند چند is_correct=True باشد
    برای true_false: دو گزینه با متن 'درست' و 'غلط'
    """

    __tablename__ = "question_options"

    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False, comment="متن گزینه")
    is_correct: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ─── Relationships ────────────────────────────────────────────────────
    question: Mapped["Question"] = relationship(back_populates="options")


class QuizAttempt(UUIDMixin, Base):
    """
    یک بار شرکت در آزمون.

    قانون: فقط INSERT — هرگز UPDATE.
    تاریخچه کامل در answers (JSONB) ذخیره می‌شود.

    ساختار answers:
    {
      "question_uuid": {
        "selected_option_ids": ["uuid1", "uuid2"],
        "text_answer": null,
        "is_correct": true,
        "score": 1
      },
      ...
    }
    """

    __tablename__ = "quiz_attempts"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quiz_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("quizzes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # اگر از مرحله onboarding آمده باشد
    step_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("program_steps.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ─── نتیجه ────────────────────────────────────────────────────────────
    score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="امتیاز کسب شده"
    )
    max_score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="حداکثر امتیاز ممکن"
    )
    percentage: Mapped[float] = mapped_column(
        Numeric(5, 2), nullable=False, default=0,
        comment="درصد — score/max_score * 100"
    )
    passed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="قبول شده؟ percentage >= pass_score"
    )

    # ─── پاسخ‌ها ─────────────────────────────────────────────────────────
    answers: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict,
        comment="تاریخچه کامل پاسخ‌ها — هرگز UPDATE نکنید"
    )

    # ─── زمان‌بندی ─────────────────────────────────────────────────────────
    duration_sec: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="مدت زمان پاسخ به ثانیه"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ─── Relationships ────────────────────────────────────────────────────
    quiz: Mapped["Quiz"] = relationship(back_populates="attempts")

    def __repr__(self) -> str:
        return (
            f"<QuizAttempt user={self.user_id} "
            f"quiz={self.quiz_id} passed={self.passed}>"
        )