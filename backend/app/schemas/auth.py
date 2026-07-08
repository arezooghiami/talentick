"""
Talentick — Auth Schemas
==========================
مدل‌های ورودی/خروجی endpoint های احراز هویت.

جریان توکن (Token Flow):
    1. POST /api/auth/login   → access_token (۶۰ دقیقه) + refresh_token (۳۰ روز)
    2. با access_token به سایر endpoint ها درخواست بزنید (Authorization: Bearer ...)
    3. وقتی access_token منقضی شد → POST /api/auth/refresh با refresh_token
       → access_token و refresh_token جدید می‌گیرید (Rotation — توکن قبلی باطل می‌شود)
    4. POST /api/auth/logout → توکن(های) فعلی را باطل می‌کند
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """
    بدنه لاگین.

    توجه: endpoint واقعی `/api/auth/login` از فرم OAuth2 استاندارد
    (application/x-www-form-urlencoded با فیلدهای username/password)
    استفاده می‌کند — این اسکیمای JSON صرفاً برای مستندسازی قرارداد
    منطقی (ایمیل + پسورد) نگه‌داشته شده و در کلاینت‌های غیر-فرم مفید است.
    """
    email: EmailStr
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """پاسخ موفق login/refresh — شامل هر دو توکن."""
    access_token: str = Field(..., description="برای Authorization: Bearer <token> در تمام درخواست‌های محافظت‌شده — اعتبار ۶۰ دقیقه")
    refresh_token: str = Field(..., description="فقط برای POST /api/auth/refresh استفاده شود — اعتبار ۳۰ روز — به‌صورت امن (نه localStorage در صورت امکان) نگه‌داری شود")
    token_type: str = "bearer"
    expires_in: int = Field(..., description="مدت اعتبار access_token به ثانیه")
    user_id: str
    org_id: str
    role: str
    full_name: str


class RefreshRequest(BaseModel):
    """بدنه‌ی POST /api/auth/refresh."""
    refresh_token: str


class LogoutRequest(BaseModel):
    """
    بدنه‌ی POST /api/auth/logout.

    refresh_token اختیاری است:
    - اگر داده شود: فقط همان session (همان دستگاه/مرورگر) خارج می‌شود.
    - اگر داده نشود: همه‌ی session های فعال کاربر (همه دستگاه‌ها) خارج می‌شوند.
    """
    refresh_token: str | None = None


class MeResponse(BaseModel):
    """پاسخ GET /api/auth/me — پروفایل کاربر لاگین‌شده."""
    id: str
    org_id: str
    org_name: str
    email: str
    full_name: str
    role: str
    is_active: bool
    avatar_url: str | None = None
    phone: str | None = None
    department: str | None = None
    position: str | None = None
    last_login_at: datetime | None = None

    model_config = {"from_attributes": True}
