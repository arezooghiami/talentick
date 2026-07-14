"""
Talentick — Quiz Schemas
==========================
دو دسته‌ی کاملاً جدا:

1) Admin (سازنده/مدیر آزمون) — شامل is_correct روی گزینه‌ها و explanation.
2) Take (کارمندی که در حال شرکت در آزمون است) — is_correct و explanation
   عمداً از پاسخ حذف شده تا پاسخ صحیح قبل از ثبت لو نرود.

بعد از ثبت پاسخ (attempt)، نتیجه (QuizAttemptResult) شامل is_correct و
explanation هست — چون آزمون تمام شده.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

QUESTION_TYPES = ("single_choice", "multi_choice", "true_false", "short_text")


# ─── Question Option ────────────────────────────────────────────────────────

class QuestionOptionCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=2000)
    is_correct: bool = False
    order_index: int = 0


class QuestionOptionAdminResponse(BaseModel):
    """شامل is_correct — فقط برای سازنده/مدیر آزمون."""
    id: str
    body: str
    is_correct: bool
    order_index: int

    model_config = {"from_attributes": True}


class QuestionOptionTakeResponse(BaseModel):
    """بدون is_correct — برای کارمندی که در حال پاسخ‌دادن است."""
    id: str
    body: str
    order_index: int

    model_config = {"from_attributes": True}


# ─── Question ────────────────────────────────────────────────────────────────

class QuestionCreate(BaseModel):
    body: str = Field(..., min_length=1)
    type: str = Field(..., description="single_choice | multi_choice | true_false | short_text")
    explanation: Optional[str] = None
    score: int = Field(1, ge=0)
    order_index: int = 0
    options: list[QuestionOptionCreate] = Field(default_factory=list)


class QuestionUpdate(BaseModel):
    body: Optional[str] = Field(None, min_length=1)
    type: Optional[str] = None
    explanation: Optional[str] = None
    score: Optional[int] = Field(None, ge=0)
    order_index: Optional[int] = None
    options: Optional[list[QuestionOptionCreate]] = Field(
        None, description="اگر ارسال شود، همه‌ی گزینه‌های قبلی این سوال جایگزین می‌شوند"
    )


class QuestionAdminResponse(BaseModel):
    id: str
    quiz_id: str
    body: str
    type: str
    explanation: Optional[str] = None
    score: int
    order_index: int
    options: list[QuestionOptionAdminResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class QuestionTakeResponse(BaseModel):
    """برای GET .../take — بدون is_correct و بدون explanation."""
    id: str
    body: str
    type: str
    score: int
    order_index: int
    options: list[QuestionOptionTakeResponse] = Field(default_factory=list)


# ─── Quiz (مدیریت — Admin) ────────────────────────────────────────────────────

class QuizCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=500)
    description: Optional[str] = None
    pass_score: int = Field(70, ge=0, le=100, description="نمره قبولی — درصد از ۱۰۰")
    time_limit_min: Optional[int] = Field(None, ge=1, description="null یعنی بدون محدودیت زمانی")
    shuffle_questions: bool = False
    shuffle_options: bool = False
    is_onboarding: bool = False
    max_attempts: Optional[int] = Field(None, ge=1, description="null یعنی نامحدود")
    org_id: Optional[str] = None  # فقط super_admin — در router enforce می‌شود


class QuizUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=500)
    description: Optional[str] = None
    pass_score: Optional[int] = Field(None, ge=0, le=100)
    time_limit_min: Optional[int] = Field(None, ge=1)
    shuffle_questions: Optional[bool] = None
    shuffle_options: Optional[bool] = None
    is_onboarding: Optional[bool] = None
    max_attempts: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None


class QuizResponse(BaseModel):
    id: str
    org_id: str
    title: str
    description: Optional[str] = None
    pass_score: int
    time_limit_min: Optional[int] = None
    shuffle_questions: bool
    shuffle_options: bool
    is_onboarding: bool
    max_attempts: Optional[int] = None
    is_active: bool
    question_count: int = 0
    created_by: Optional[str] = None
    created_by_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class QuizDetailResponse(QuizResponse):
    """برای ادمین — شامل سوالات با پاسخ صحیح."""
    questions: list[QuestionAdminResponse] = Field(default_factory=list)


class QuizListResponse(BaseModel):
    items: list[QuizResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ─── Take a Quiz (کارمند) ─────────────────────────────────────────────────────

class QuizTakeResponse(BaseModel):
    """چیزی که کارمند قبل از شروع پاسخ‌گویی می‌بیند — بدون پاسخ صحیح."""
    id: str
    title: str
    description: Optional[str] = None
    pass_score: int
    time_limit_min: Optional[int] = None
    max_attempts: Optional[int] = None
    attempts_used: int
    can_attempt: bool = Field(..., description="False اگر max_attempts پر شده یا آزمون غیرفعال باشد")
    questions: list[QuestionTakeResponse] = Field(default_factory=list)


class AnswerSubmit(BaseModel):
    selected_option_ids: list[str] = Field(default_factory=list)
    text_answer: Optional[str] = None


class QuizAttemptSubmit(BaseModel):
    started_at: datetime = Field(..., description="زمان شروع پاسخ‌گویی (سمت کلاینت) — برای محاسبه duration_sec")
    answers: dict[str, AnswerSubmit] = Field(
        default_factory=dict, description="نگاشت question_id → پاسخ کاربر به آن سوال"
    )


class AnswerResult(BaseModel):
    """نتیجه‌ی هر سوال بعد از ثبت attempt — شامل پاسخ صحیح و توضیح."""
    question_id: str
    question_body: str
    question_type: str
    selected_option_ids: list[str] = Field(default_factory=list)
    text_answer: Optional[str] = None
    is_correct: Optional[bool] = Field(
        None, description="null برای سوالات تشریحی (short_text) — نیازمند نمره‌دهی دستی، خارج از scope فعلی"
    )
    score: int
    max_score: int
    explanation: Optional[str] = None
    correct_option_ids: list[str] = Field(default_factory=list)


class QuizAttemptResult(BaseModel):
    id: str
    quiz_id: str
    quiz_title: str
    score: int
    max_score: int
    percentage: float
    passed: bool
    duration_sec: Optional[int] = None
    started_at: datetime
    completed_at: datetime
    answers: list[AnswerResult] = Field(default_factory=list)


class QuizAttemptSummary(BaseModel):
    """یک سطر در تاریخچه‌ی تلاش‌های من — بدون جزئیات پاسخ‌ها."""
    id: str
    score: int
    max_score: int
    percentage: float
    passed: bool
    duration_sec: Optional[int] = None
    started_at: datetime
    completed_at: datetime

    model_config = {"from_attributes": True}


# ─── Attempts (گزارش ادمین) ────────────────────────────────────────────────────

class QuizAttemptAdminRow(BaseModel):
    """یک سطر در گزارش تلاش‌های یک آزمون — برای ادمین/گزارش‌گیری."""
    id: str
    user_id: str
    user_full_name: str
    user_email: str
    score: int
    max_score: int
    percentage: float
    passed: bool
    duration_sec: Optional[int] = None
    started_at: datetime
    completed_at: datetime


class QuizAttemptListResponse(BaseModel):
    items: list[QuizAttemptAdminRow]
    total: int
    page: int
    page_size: int
    total_pages: int
