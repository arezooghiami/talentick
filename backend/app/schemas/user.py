"""
Talentick — User Schemas
==========================
Pydantic models برای User endpoints.

department (رشته نمایشی) از رابطه‌ی Department خوانده می‌شود — برای
تنظیم واقعی دپارتمان/پست/مدیر مستقیم کاربر از dept_id / position_id /
manager_id استفاده کنید (که حالا در Create/Update موجودند).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.phone import normalize_phone

# نقش‌های مجاز سیستم — باید با app.models.user.VALID_ROLES هماهنگ باشد
ROLE_PATTERN = "^(super_admin|org_admin|manager|employee)$"


def _validate_phone(v: str) -> str:
    try:
        return normalize_phone(v)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc


def _validate_phone_optional(v: str | None) -> str | None:
    return _validate_phone(v) if v is not None else None


# ─── Request: Create ──────────────────────────────────────────────────────────

class UserCreateRequest(BaseModel):
    """
    ساخت کاربر جدید.

    دسترسی:
    - super_admin: می‌تواند org_id هر سازمانی و هر role ای بدهد؛ تنها
      نقشی که می‌تواند org_id را خالی (None) بگذارد — یعنی کاربر
      General/Public بسازد — همان super_admin است.
    - org_admin: org_id باید سازمان خودش باشد (در router enforce می‌شود)
                 و فقط می‌تواند role های org_admin/manager/employee بسازد
                 — نمی‌تواند کاربر General بسازد.
    - manager: اجازه ساخت کاربر ندارد

    نکته: کاربر General (org_id=None) اجباراً role="employee" است و
    dept_id/position_id/manager_id او باید خالی باشند — در
    user_service.create_user اعتبارسنجی می‌شود.
    """
    phone: str = Field(..., description="شماره موبایل — شناسه‌ی اصلی لاگین، 09xxxxxxxxx")
    email: EmailStr | None = None
    full_name: str = Field(..., min_length=2, max_length=255)
    role: str = Field("employee", pattern=ROLE_PATTERN)
    org_id: str | None = None
    password: str = Field(..., min_length=8)
    dept_id: str | None = None
    position_id: str | None = None
    manager_id: str | None = None
    employee_onboarding_program_id: str | None = Field(
        None,
        description=(
            "کارمند جدید است — انتخاب صریح یک مسیر Employee Onboarding "
            "(OnboardingProgram با purpose=employee_onboarding) برای ثبت‌نام خودکار این کاربر در آن. "
            "خالی یعنی این کاربر نیازی به Employee Onboarding ندارد."
        ),
    )

    @field_validator("phone")
    @classmethod
    def _normalize_phone(cls, v: str) -> str:
        return _validate_phone(v)


# ─── Request: Update ──────────────────────────────────────────────────────────

class UserUpdateRequest(BaseModel):
    """
    ویرایش کاربر — همه فیلدها اختیاری (partial update).

    دسترسی:
    - super_admin: هر فیلدی روی هر کاربری
    - org_admin/manager: فقط کاربران سازمان خودشان — role نمی‌توانند به
      super_admin تغییر دهند (در router enforce می‌شود)

    نکته: برای پاک کردن dept_id/position_id/manager_id مقدار رشته
    خالی "" بفرستید (None یعنی «این فیلد تغییر نکند»).
    """
    full_name: str | None = Field(None, min_length=2, max_length=255)
    email: EmailStr | None = None
    role: str | None = Field(None, pattern=ROLE_PATTERN)
    phone: str | None = None
    is_active: bool | None = None
    dept_id: str | None = None
    position_id: str | None = None
    manager_id: str | None = None
    employee_onboarding_program_id: str | None = Field(
        None,
        description=(
            "تخصیص/تغییر مسیر Employee Onboarding این کاربر — ارسال‌نشدن یعنی بدون تغییر. "
            "اگر کاربر از قبل مسیری داشت، این مقدار Enrollment جدیدی می‌سازد (Idempotent روی همان مسیر)."
        ),
    )

    @field_validator("phone")
    @classmethod
    def _normalize_phone(cls, v: str | None) -> str | None:
        return _validate_phone_optional(v)


# ─── Response ─────────────────────────────────────────────────────────────────

class UserListItem(BaseModel):
    """یک سطر در جدول کاربران."""
    id: str
    full_name: str
    email: str | None = None
    phone: str
    role: str
    department: str | None = None
    position: str | None = None
    org_id: str | None = None
    org_name: str | None = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserDetail(BaseModel):
    """جزئیات کامل کاربر."""
    id: str
    full_name: str
    email: str | None = None
    role: str
    department: str | None = None
    dept_id: str | None = None
    position: str | None = None
    position_id: str | None = None
    manager_id: str | None = None
    manager_name: str | None = None
    phone: str
    org_id: str | None = None
    is_active: bool
    must_change_password: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Password Reset (توسط ادمین) ───────────────────────────────────────────

class PasswordResetResponse(BaseModel):
    """
    پاسخ POST /api/users/{id}/reset-password.

    temp_password فقط همین یک‌بار در همین پاسخ نمایش داده می‌شود — در هیچ
    جای دیگری (لاگ، دیتابیس) به‌صورت خوانا ذخیره نمی‌شود. ادمین باید آن
    را دستی (تلفن/حضوری — نه ایمیل/پیامک ناامن) به کاربر بدهد.
    """
    user_id: str
    temp_password: str = Field(..., description="رمز موقت — فقط همین یک‌بار قابل مشاهده است")
    message: str = "رمز عبور کاربر Reset شد — این رمز را فقط از کانال امن به کاربر بدهید"


class PaginatedUsers(BaseModel):
    """پاسخ صفحه‌بندی‌شده لیست کاربران."""
    items: list[UserListItem]
    total: int
    page: int
    per_page: int
    pages: int


# ─── Import/Export (Excel) ────────────────────────────────────────────────────

class UserImportRowError(BaseModel):
    """خطای مربوط به یک سطر خاص در فایل Import."""
    row: int = Field(..., description="شماره سطر در فایل اکسل (شامل هدر)")
    phone: str | None = None
    email: str | None = None
    message: str


class CreatedUserCredential(BaseModel):
    """
    موبایل/ایمیل + رمز موقت یک کاربر تازه‌ساخته‌شده از Import.

    چون سرویس ایمیل/پیامک برای این جریان وجود ندارد، این تنها جایی است
    که رمز موقت به‌صورت خوانا در دسترس است — ادمین باید آن را دستی
    (کانال امن) به کاربر بدهد. کاربر با اولین ورود موظف به تغییر رمز است
    (must_change_password=True).
    """
    phone: str
    email: str | None = None
    temp_password: str


class UserImportResult(BaseModel):
    """گزارش کامل نتیجه Import گروهی کاربران از Excel."""
    total_rows: int
    created: int
    updated: int
    skipped: int
    errors: list[UserImportRowError] = Field(default_factory=list)
    created_users: list[CreatedUserCredential] = Field(
        default_factory=list,
        description="ایمیل + رمز موقت هر کاربر تازه‌ساخته‌شده — فقط همین یک‌بار در دسترس است",
    )