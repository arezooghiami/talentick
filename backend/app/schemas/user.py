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

from pydantic import BaseModel, EmailStr, Field

# نقش‌های مجاز سیستم — باید با app.models.user.VALID_ROLES هماهنگ باشد
ROLE_PATTERN = "^(super_admin|org_admin|manager|employee)$"


# ─── Request: Create ──────────────────────────────────────────────────────────

class UserCreateRequest(BaseModel):
    """
    ساخت کاربر جدید.

    دسترسی:
    - super_admin: می‌تواند org_id هر سازمانی و هر role ای بدهد
    - org_admin: org_id باید سازمان خودش باشد (در router enforce می‌شود)
                 و فقط می‌تواند role های org_admin/manager/employee بسازد
    - manager: اجازه ساخت کاربر ندارد
    """
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    role: str = Field("employee", pattern=ROLE_PATTERN)
    org_id: str
    password: str = Field(..., min_length=8)
    phone: str | None = None
    dept_id: str | None = None
    position_id: str | None = None
    manager_id: str | None = None


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


# ─── Response ─────────────────────────────────────────────────────────────────

class UserListItem(BaseModel):
    """یک سطر در جدول کاربران."""
    id: str
    full_name: str
    email: str
    role: str
    department: str | None = None
    position: str | None = None
    org_id: str
    org_name: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserDetail(BaseModel):
    """جزئیات کامل کاربر."""
    id: str
    full_name: str
    email: str
    role: str
    department: str | None = None
    dept_id: str | None = None
    position: str | None = None
    position_id: str | None = None
    manager_id: str | None = None
    manager_name: str | None = None
    phone: str | None = None
    org_id: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedUsers(BaseModel):
    """پاسخ صفحه‌بندی‌شده لیست کاربران."""
    items: list[UserListItem]
    total: int
    page: int
    per_page: int
    pages: int