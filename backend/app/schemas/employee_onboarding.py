"""
Talentick — Employee Onboarding Schemas
===========================================
فرآیند ورود کارمند جدید — بعد از بازطراحی مشترک با ماژول آنبوردینگ،
دیگر یک Config/Progress جداگانه ندارد: خودِ «مسیر ورود کارمند جدید» یک
app.models.onboarding.OnboardingProgram با purpose="employee_onboarding"
است (schemas/onboarding.py را ببینید — CRUD مسیر/مرحله از همان‌جاست).

این فایل فقط شامل:
    - کاتالوگ مدارک سازمان (EmployeeDocumentType) — CRUD مدیریتی
    - ثبت مدرک/مقدار توسط کارمند (EmployeeDocumentSubmission)
    - وضعیت کامل یک کاربر (هم «مسیر ورود من» خودش، هم نمای Monitoring
      مدیریتی و نمایش مدارک در پروفایل کاربر)
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.employee_onboarding import DOCUMENT_INPUT_TYPES, DOCUMENT_SUBMISSION_STATUSES

__all__ = ["DOCUMENT_SUBMISSION_STATUSES", "DOCUMENT_INPUT_TYPES"]

INPUT_TYPE_PATTERN = "^(file|text)$"


# ─── EmployeeDocumentType (کاتالوگ مدارک سازمان) ────────────────────────────

class EmployeeDocumentTypeCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = Field(
        None, description="محل توضیح گزینه‌های جایگزین («پایان خدمت یا کارت معافیت») و کمیت («۲ قطعه») در صورت نیاز"
    )
    input_type: str = Field("file", pattern=INPUT_TYPE_PATTERN, description="file | text — مثال text: شماره حساب بانکی")
    is_required: bool = True
    allowed_extensions: list[str] = Field(
        default_factory=list,
        description="فقط برای input_type=file — خالی یعنی همه‌ی فرمت‌های مجاز سراسری (core/storage.ALLOWED_EXTENSIONS) پذیرفته می‌شوند",
    )
    max_size_mb: Optional[int] = Field(None, ge=1, le=200, description="فقط برای input_type=file — خالی یعنی از سقف سراسری استفاده شود")
    template_file_url: Optional[str] = Field(
        None, description="فقط برای input_type=file — آدرس فرم خام (از /api/employee-onboarding/document-types/upload-template)"
    )
    order_index: int = 0
    is_active: bool = True
    org_id: Optional[str] = Field(None, description="فقط super_admin — در router enforce می‌شود")


class EmployeeDocumentTypeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    input_type: Optional[str] = Field(None, pattern=INPUT_TYPE_PATTERN)
    is_required: Optional[bool] = None
    allowed_extensions: Optional[list[str]] = None
    max_size_mb: Optional[int] = Field(None, ge=1, le=200)
    template_file_url: Optional[str] = Field(None, description='رشته خالی "" یعنی پاک‌کردن')
    order_index: Optional[int] = None
    is_active: Optional[bool] = None


class EmployeeDocumentTypeResponse(BaseModel):
    id: str
    org_id: str
    name: str
    description: Optional[str] = None
    input_type: str = "file"
    is_required: bool
    allowed_extensions: list[str] = Field(default_factory=list)
    max_size_mb: Optional[int] = None
    template_file_url: Optional[str] = None
    order_index: int
    is_active: bool
    submission_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── وضعیت هر مدرک برای یک کاربر مشخص ────────────────────────────────────────

class DocumentTypeStatusResponse(BaseModel):
    document_type_id: str
    document_type_name: str
    description: Optional[str] = None
    input_type: str = "file"
    is_required: bool
    allowed_extensions: list[str] = Field(default_factory=list)
    max_size_mb: Optional[int] = None
    template_file_url: Optional[str] = None
    status: str = Field(..., description="not_uploaded | approved | under_review | rejected")
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    text_value: Optional[str] = None
    rejection_reason: Optional[str] = None
    uploaded_at: Optional[datetime] = None


class DocumentsStatus(BaseModel):
    completed: bool = Field(..., description="همه‌ی مدارک اجباری فعال سازمان تأیید شده‌اند")
    required_count: int = 0
    submitted_count: int = 0
    items: list[DocumentTypeStatusResponse] = Field(default_factory=list)


class DocumentSubmissionResponse(BaseModel):
    id: str
    document_type_id: str
    document_type_name: str
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    text_value: Optional[str] = None
    status: str
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TextValueSubmitRequest(BaseModel):
    """بدنه‌ی POST برای ثبت مقدار یک قلم input_type=text (مثال: شماره حساب بانکی)."""
    text_value: str = Field(..., min_length=1, max_length=1000)


# ─── وضعیت کامل کاربر — «مسیر ورود من» + نمای مدیریتی Monitoring/پروفایل ────

class EmployeeOnboardingEnrollmentSummary(BaseModel):
    """خلاصه‌ی یک ثبت‌نام کاربر در یک مسیر با purpose=employee_onboarding."""
    enrollment_id: str
    program_id: str
    program_name: str
    enrolled_at: datetime
    deadline_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress_pct: int = 0
    steps_total: int = 0
    steps_completed: int = 0


class EmployeeOnboardingStatusResponse(BaseModel):
    """
    وضعیت کامل Employee Onboarding یک کاربر — هم برای «مسیر ورود من»
    (GET /employee-onboarding/me/status) و هم نمای مدیریتی (Monitoring +
    بخش «مدارک» در پروفایل کاربر) استفاده می‌شود.
    """
    user_id: str
    user_name: str
    user_email: Optional[str] = None
    is_blocked: bool = Field(..., description="آیا این کاربر همچنان از مشاهده‌ی محتوای سیستم مسدود است")
    last_activity_at: Optional[datetime] = None
    enrollments: list[EmployeeOnboardingEnrollmentSummary] = Field(
        default_factory=list, description="مسیرهای Employee Onboarding که این کاربر در آن‌ها ثبت‌نام شده"
    )
    documents: DocumentsStatus


class EmployeeOnboardingStatusListResponse(BaseModel):
    items: list[EmployeeOnboardingStatusResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
