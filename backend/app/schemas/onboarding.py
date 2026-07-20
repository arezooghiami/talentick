"""
Talentick — Onboarding Schemas
=================================
برنامه‌ی آشنایی سازمانی (Learning Journey): OnboardingProgram → ProgramStep
→ UserProgramEnrollment → UserStepProgress.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

STEP_TYPES = ("content", "quiz", "document_upload", "custom")
STEP_STATUSES = ("not_started", "in_progress", "completed", "skipped")


# ─── ProgramStep ─────────────────────────────────────────────────────────────

class ProgramStepCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=500)
    description: Optional[str] = None
    type: str = Field(..., description="content | quiz | document_upload | custom")
    content_id: Optional[str] = None
    quiz_id: Optional[str] = None
    is_required: bool = True
    order_index: int = 0
    points_override: Optional[int] = Field(None, ge=0, le=1000, description="امتیاز اختصاصی این مرحله — خالی یعنی مقدار سراسری")


class ProgramStepUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=500)
    description: Optional[str] = None
    type: Optional[str] = None
    content_id: Optional[str] = None
    quiz_id: Optional[str] = None
    is_required: Optional[bool] = None
    order_index: Optional[int] = None
    points_override: Optional[int] = Field(None, ge=0, le=1000)


class ProgramStepResponse(BaseModel):
    id: str
    program_id: str
    title: str
    description: Optional[str] = None
    type: str
    content_id: Optional[str] = None
    content_title: Optional[str] = None
    quiz_id: Optional[str] = None
    quiz_title: Optional[str] = None
    is_required: bool
    order_index: int
    points_override: Optional[int] = None

    model_config = {"from_attributes": True}


# ─── OnboardingProgram ─────────────────────────────────────────────────────

class OnboardingProgramCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=500)
    description: Optional[str] = None
    target_roles: list[str] = Field(
        default_factory=list, description="خالی یعنی همه‌ی نقش‌ها"
    )
    target_dept_id: Optional[str] = Field(None, description="خالی یعنی همه‌ی واحدها")
    is_default: bool = Field(
        False, description="ثبت‌نام خودکار برای هر کارمند جدیدی که با این نقش/واحد ساخته می‌شود"
    )
    deadline_days: Optional[int] = Field(None, ge=1, description="مهلت تکمیل به روز از لحظه‌ی ثبت‌نام")
    is_active: bool = True
    points_override: Optional[int] = Field(None, ge=0, le=1000, description="امتیاز اختصاصی تکمیل کامل این برنامه — خالی یعنی مقدار سراسری")
    org_id: Optional[str] = Field(None, description="فقط super_admin — در router enforce می‌شود")


class OnboardingProgramUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=500)
    description: Optional[str] = None
    target_roles: Optional[list[str]] = None
    target_dept_id: Optional[str] = Field(
        None, description='رشته خالی "" یعنی پاک‌کردن (همه واحدها) — ارسال‌نشدن یعنی بدون تغییر'
    )
    is_default: Optional[bool] = None
    deadline_days: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None
    points_override: Optional[int] = Field(None, ge=0, le=1000)


class OnboardingProgramResponse(BaseModel):
    id: str
    org_id: str
    org_name: Optional[str] = None
    name: str
    description: Optional[str] = None
    target_roles: list[str] = Field(default_factory=list)
    target_dept_id: Optional[str] = None
    target_dept_name: Optional[str] = None
    is_default: bool
    deadline_days: Optional[int] = None
    is_active: bool
    points_override: Optional[int] = None
    step_count: int = 0
    enrollment_count: int = 0
    created_by: Optional[str] = None
    created_by_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OnboardingProgramDetailResponse(OnboardingProgramResponse):
    steps: list[ProgramStepResponse] = Field(default_factory=list)


class OnboardingProgramListResponse(BaseModel):
    items: list[OnboardingProgramResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ─── Enrollment (نمای مدیریتی) ────────────────────────────────────────────

class EnrollRequest(BaseModel):
    user_ids: list[str] = Field(..., min_length=1)


class EnrollmentResponse(BaseModel):
    id: str
    program_id: str
    user_id: str
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    enrolled_at: datetime
    deadline_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress_pct: int
    steps_total: int = 0
    steps_completed: int = 0

    model_config = {"from_attributes": True}


class EnrollmentListResponse(BaseModel):
    items: list[EnrollmentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ─── نمای شخصی کارمند («مسیر آنبوردینگ من») ────────────────────────────────

class MyStepProgressResponse(BaseModel):
    step_id: str
    title: str
    description: Optional[str] = None
    type: str
    content_id: Optional[str] = None
    content_title: Optional[str] = None
    quiz_id: Optional[str] = None
    quiz_title: Optional[str] = None
    is_required: bool
    order_index: int
    status: str
    notes: Optional[str] = None
    completed_at: Optional[datetime] = None


class MyEnrollmentResponse(BaseModel):
    enrollment_id: str
    program_id: str
    program_name: str
    program_description: Optional[str] = None
    enrolled_at: datetime
    deadline_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress_pct: int
    steps_total: int
    steps_completed: int


class MyEnrollmentDetailResponse(MyEnrollmentResponse):
    steps: list[MyStepProgressResponse] = Field(default_factory=list)


class StepCompleteRequest(BaseModel):
    notes: Optional[str] = Field(None, max_length=2000)
