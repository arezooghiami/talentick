"""
Talentick — Auth Router
==========================
احراز هویت کامل مبتنی بر JWT با Access + Refresh Token (Rotation).

Routes:
    POST /api/auth/login    → ورود با ایمیل/پسورد → access_token + refresh_token
    POST /api/auth/refresh  → صدور access_token جدید با refresh_token معتبر
    POST /api/auth/logout   → باطل کردن session فعلی یا همه‌ی session ها
    GET  /api/auth/me       → پروفایل کامل کاربر لاگین‌شده

امنیت:
    - حداکثر ۵ تلاش ورود ناموفق در هر ۵ دقیقه به ازای (IP + ایمیل) —
      جلوگیری از Brute Force (core/rate_limit.py).
    - پیام خطای ورود ناموفق عمداً یکسان است («ایمیل یا رمز عبور اشتباه
      است») تا مهاجم نتواند تشخیص دهد ایمیل موجود است یا نه (جلوگیری
      از User Enumeration).
    - Refresh Token Rotation: هر استفاده از refresh_token، آن را باطل و
      یک توکن جدید صادر می‌کند.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UnauthorizedError
from app.core.rate_limit import login_rate_limiter
from app.database import get_db
from app.dependencies import CurrentUser
from app.schemas.auth import LogoutRequest, MeResponse, RefreshRequest, TokenResponse
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

_INVALID_CREDENTIALS_MSG = "ایمیل یا رمز عبور اشتباه است"


def _client_key(request: Request, username: str) -> str:
    """کلید Rate Limit: ترکیب IP و ایمیل — هم جلوی brute-force روی یک اکانت را می‌گیرد هم روی یک IP."""
    client_host = request.client.host if request.client else "unknown"
    return f"{client_host}:{username.lower()}"


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="ورود به سیستم",
    description="""
    ورود با ایمیل (فیلد `username` در فرم) و پسورد — استاندارد OAuth2
    Password Flow، یعنی بدنه‌ی درخواست باید
    `application/x-www-form-urlencoded` با فیلدهای `username` و
    `password` باشد (نه JSON).

    **پاسخ موفق:** `access_token` (۶۰ دقیقه اعتبار) و `refresh_token`
    (۳۰ روز اعتبار). `access_token` را در هدر
    `Authorization: Bearer <token>` تمام درخواست‌های بعدی قرار دهید.

    **خطاها:**
    - `401` — ایمیل یا پسورد اشتباه، یا حساب غیرفعال است.
    - `429` — بیش از ۵ تلاش ناموفق در ۵ دقیقه اخیر (Rate Limit).
    """,
    responses={
        401: {"description": "ایمیل یا پسورد اشتباه است، یا حساب غیرفعال است"},
        429: {"description": "تعداد تلاش‌های ورود بیش از حد مجاز — کمی صبر کنید"},
    },
)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    rate_key = _client_key(request, form_data.username)
    login_rate_limiter.check(rate_key)

    user = await auth_service.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, _INVALID_CREDENTIALS_MSG)

    login_rate_limiter.reset(rate_key)
    return await auth_service.create_session(db, user)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="تمدید session با refresh_token",
    description="""
    وقتی `access_token` منقضی شد (بعد از ۶۰ دقیقه)، به‌جای اجبار کاربر
    به لاگین دوباره، فرانت باید این endpoint را با `refresh_token`
    ذخیره‌شده صدا بزند.

    **Rotation:** `refresh_token` قبلی بلافاصله باطل می‌شود و یک جفت
    توکن کاملاً جدید صادر می‌شود — همیشه توکن جدید را جایگزین توکن قبلی
    در storage فرانت کنید.

    **خطاها:**
    - `401` — refresh_token نامعتبر، منقضی، از قبل استفاده/باطل‌شده،
      یا کاربر دیگر فعال نیست. در این حالت فرانت باید کاربر را به صفحه
      لاگین هدایت کند.
    """,
    responses={401: {"description": "refresh_token نامعتبر یا منقضی — نیاز به ورود مجدد"}},
)
async def refresh(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    try:
        return await auth_service.refresh_session(db, body.refresh_token)
    except UnauthorizedError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, exc.detail)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="خروج از سیستم",
    description="""
    نیازمند `access_token` معتبر در هدر Authorization.

    - اگر `refresh_token` در بدنه داده شود: فقط همان session (همان
      دستگاه/مرورگر) خارج می‌شود.
    - اگر بدنه خالی/بدون `refresh_token` باشد: همه‌ی session های فعال
      کاربر (همه دستگاه‌ها) باطل می‌شوند — «خروج از همه دستگاه‌ها».

    توجه: `access_token` فعلی تا زمان انقضای طبیعی‌اش (حداکثر ۶۰ دقیقه)
    در تئوری قابل استفاده می‌ماند چون JWT stateless است — فقط
    `refresh_token` بلافاصله باطل می‌شود. برای invalidation فوری
    access_token هم، فاز بعد باید یک Token Blocklist اضافه شود.
    """,
)
async def logout(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    body: LogoutRequest | None = None,
) -> None:
    refresh_token = body.refresh_token if body else None
    await auth_service.revoke_session(db, current_user, refresh_token)


@router.get(
    "/me",
    response_model=MeResponse,
    summary="پروفایل کاربر فعلی",
    description="پروفایل کامل کاربر لاگین‌شده — شامل نام سازمان، دپارتمان و سمت. نیازمند access_token معتبر.",
    responses={401: {"description": "توکن نامعتبر/منقضی یا ارسال نشده است"}},
)
async def me(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    return await auth_service.get_me(db, current_user)
