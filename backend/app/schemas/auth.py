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

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.phone import normalize_phone


class LoginRequest(BaseModel):
    """
    بدنه لاگین.

    توجه: endpoint واقعی `/api/auth/login` از فرم OAuth2 استاندارد
    (application/x-www-form-urlencoded با فیلدهای username/password)
    استفاده می‌کند — این اسکیمای JSON صرفاً برای مستندسازی قرارداد
    منطقی نگه‌داشته شده و در کلاینت‌های غیر-فرم مفید است. فیلد `username`
    می‌تواند شماره موبایل (09xxxxxxxxx) یا ایمیل کاربر باشد.
    """
    username: str = Field(..., description="شماره موبایل یا ایمیل کاربر")
    password: str = Field(..., min_length=1)


class ForgotPasswordRequest(BaseModel):
    """بدنه‌ی POST /api/auth/forgot-password — درخواست کد OTP برای reset رمز."""
    phone: str = Field(..., description="شماره موبایل ثبت‌شده — 09xxxxxxxxx")

    @field_validator("phone")
    @classmethod
    def _normalize(cls, v: str) -> str:
        try:
            return normalize_phone(v)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc


class ForgotPasswordResponse(BaseModel):
    """
    پاسخ POST /api/auth/forgot-password.

    پیام همیشه یکسان است — چه شماره ثبت‌شده باشد چه نه — تا مهاجم نتواند
    وجود/عدم‌وجود یک شماره را در سیستم تشخیص دهد (User Enumeration).
    """
    message: str = "در صورت ثبت بودن این شماره، کد تایید برای آن پیامک شد"
    expires_in_seconds: int


class VerifyOtpAndResetPasswordRequest(BaseModel):
    """بدنه‌ی POST /api/auth/reset-password — تایید کد OTP + تنظیم رمز جدید."""
    phone: str = Field(..., description="شماره موبایلی که کد برایش ارسال شده")
    code: str = Field(..., min_length=4, max_length=8, description="کد تایید پیامکی")
    new_password: str = Field(..., min_length=8)

    @field_validator("phone")
    @classmethod
    def _normalize(cls, v: str) -> str:
        try:
            return normalize_phone(v)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc


class TokenResponse(BaseModel):
    """پاسخ موفق login/refresh/change-password — شامل هر دو توکن."""
    access_token: str = Field(..., description="برای Authorization: Bearer <token> در تمام درخواست‌های محافظت‌شده — اعتبار ۶۰ دقیقه")
    refresh_token: str = Field(..., description="فقط برای POST /api/auth/refresh استفاده شود — اعتبار ۳۰ روز — به‌صورت امن (نه localStorage در صورت امکان) نگه‌داری شود")
    token_type: str = "bearer"
    expires_in: int = Field(..., description="مدت اعتبار access_token به ثانیه")
    user_id: str
    org_id: str | None = Field(None, description="null یعنی کاربر General/Public (بدون سازمان)")
    role: str
    full_name: str
    must_change_password: bool = Field(
        False,
        description="اگر True باشد، کاربر تا فراخوانی موفق POST /api/auth/change-password به هیچ endpoint دیگری دسترسی ندارد",
    )
    has_seen_welcome: bool = Field(
        False,
        description="اگر False باشد، فرانت باید ۳ صفحه‌ی welcome را نشان دهد و بعد POST /api/auth/welcome-complete را صدا بزند",
    )


class ChangePasswordRequest(BaseModel):
    """بدنه‌ی POST /api/auth/change-password — نیازمند دانستن رمز فعلی."""
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)


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
    org_id: str | None = None
    org_name: str | None = None
    email: str | None = None
    full_name: str
    role: str
    is_active: bool
    avatar_url: str | None = None
    phone: str
    department: str | None = None
    position: str | None = None
    last_login_at: datetime | None = None
    must_change_password: bool = False
    has_seen_welcome: bool = False

    model_config = {"from_attributes": True}
