"""
Talentick — Auth Service
===========================
احراز هویت + مدیریت کامل چرخه‌ی JWT (access + refresh با Rotation).

قوانین امنیتی:
- پسورد هرگز plain-text نیست (bcrypt — در core/security.py)
- خودِ refresh token هرگز در DB ذخیره نمی‌شود — فقط SHA256 hash آن
  (جدول refresh_tokens) — دقیقاً مثل پسورد، تا نشت دیتابیس مساوی با
  لو رفتن session های فعال نباشد.
- Refresh Token Rotation: هر بار /refresh صدا زده شود، توکن قبلی
  بلافاصله revoke و یک توکن کاملاً جدید صادر می‌شود. اگر یک refresh
  token دزدیده‌شده و استفاده‌شده دوباره استفاده شود (چون قبلی revoke
  شده)، درخواست رد می‌شود — این الگو به‌عنوان یکی از نشانه‌های سرقت
  توکن قابل تشخیص است (پیشنهاد فاز بعد: revoke زنجیره‌ای در صورت
  reuse detection).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    generate_temp_password,
    hash_password,
    hash_token,
    verify_password,
)
from app.core.exceptions import BadRequestError, UnauthorizedError
from app.models.organization import Organization
from app.models.user import RefreshToken, User


# ─── Authentication ───────────────────────────────────────────────────────

async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    """ایمیل و پسورد را بررسی می‌کند — None اگر نامعتبر یا کاربر غیرفعال باشد."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    return user


# ─── Session (Access + Refresh Token) ──────────────────────────────────────

def _token_payload(user: User) -> dict:
    return {"sub": str(user.id), "org_id": str(user.org_id), "role": user.role}


async def create_session(db: AsyncSession, user: User) -> dict:
    """
    یک session جدید برای کاربر می‌سازد: access_token + refresh_token.

    refresh_token به‌صورت hash‌شده در DB ذخیره می‌شود تا بعداً قابل
    revoke باشد. last_login_at کاربر هم به‌روزرسانی می‌شود.
    """
    access_token = create_access_token(_token_payload(user))
    refresh_token = create_refresh_token(_token_payload(user))

    db.add(
        RefreshToken(
            id=uuid.uuid4(),
            user_id=user.id,
            org_id=user.org_id,
            token_hash=hash_token(refresh_token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
            created_at=datetime.now(timezone.utc),
        )
    )
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    return _build_token_response(user, access_token, refresh_token)


async def refresh_session(db: AsyncSession, refresh_token: str) -> dict:
    """
    یک access_token جدید (+ refresh_token جدید — Rotation) صادر می‌کند.

    خطاها:
    - UnauthorizedError: توکن نامعتبر/منقضی/از قبل revoke شده، یا
      کاربر دیگر فعال نیست.
    """
    try:
        payload = decode_refresh_token(refresh_token)
    except UnauthorizedError:
        raise UnauthorizedError("Refresh token نامعتبر یا منقضی شده است")

    token_hash = hash_token(refresh_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    stored = result.scalar_one_or_none()

    if stored is None or not stored.is_valid:
        raise UnauthorizedError("این session دیگر معتبر نیست — لطفاً دوباره وارد شوید")

    user_id_raw = payload.get("sub")
    try:
        user_id = uuid.UUID(user_id_raw)
    except (TypeError, ValueError):
        raise UnauthorizedError("Refresh token نامعتبر است")

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("کاربر یافت نشد یا غیرفعال است")

    # ─── Rotation: توکن قدیمی فوراً باطل می‌شود ────────────────────────
    stored.revoked_at = datetime.now(timezone.utc)

    new_access = create_access_token(_token_payload(user))
    new_refresh = create_refresh_token(_token_payload(user))
    db.add(
        RefreshToken(
            id=uuid.uuid4(),
            user_id=user.id,
            org_id=user.org_id,
            token_hash=hash_token(new_refresh),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
            created_at=datetime.now(timezone.utc),
        )
    )
    await db.commit()

    return _build_token_response(user, new_access, new_refresh)


async def revoke_session(db: AsyncSession, user: User, refresh_token: str | None) -> None:
    """
    Logout. اگر refresh_token داده شود فقط همان session باطل می‌شود،
    در غیر این صورت همه session های فعال کاربر (همه دستگاه‌ها) باطل می‌شوند.
    """
    if refresh_token:
        token_hash = hash_token(refresh_token)
        result = await db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.user_id == user.id,
            )
        )
        stored = result.scalar_one_or_none()
        if stored and stored.revoked_at is None:
            stored.revoked_at = datetime.now(timezone.utc)
    else:
        result = await db.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user.id,
                RefreshToken.revoked_at.is_(None),
            )
        )
        for stored in result.scalars().all():
            stored.revoked_at = datetime.now(timezone.utc)

    await db.commit()


def _build_token_response(user: User, access_token: str, refresh_token: str) -> dict:
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
        "user_id": str(user.id),
        "org_id": str(user.org_id),
        "role": user.role,
        "full_name": user.full_name,
        "must_change_password": user.must_change_password,
    }


# ─── Password Management (بدون سرویس ایمیل — طبق تصمیم محصول) ──────────────
# رمز اولیه/Reset همیشه توسط یک ادمین (نه خودِ کاربر) ساخته و دستی (تلفن/
# حضوری) به کاربر داده می‌شود. برای جلوگیری از باقی‌ماندن دائمی دانشِ رمز
# نزد ادمین، must_change_password=True ست می‌شود و طبق
# dependencies.get_current_user، کاربر تا تغییر رمز به هیچ endpoint دیگری
# دسترسی ندارد.

async def _revoke_all_sessions(db: AsyncSession, user: User) -> None:
    """همه‌ی refresh token های فعال کاربر را باطل می‌کند (خروج از همه دستگاه‌ها)."""
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    now = datetime.now(timezone.utc)
    for stored in result.scalars().all():
        stored.revoked_at = now


async def change_password(
    db: AsyncSession, user: User, current_password: str, new_password: str
) -> dict:
    """
    تغییر رمز توسط خودِ کاربر (نیازمند دانستن رمز فعلی).

    - همه session های قبلی (روی همه دستگاه‌ها) باطل می‌شوند — چون رمز قبلی
      ممکن است نزد شخص دیگری (ادمین/مهاجم) هم شناخته‌شده بوده باشد.
    - یک access/refresh token جدید بلافاصله صادر می‌شود تا کاربر مجبور به
      لاگین دوباره نباشد.
    - خطاها: BadRequestError اگر رمز فعلی اشتباه باشد.
    """
    if not verify_password(current_password, user.hashed_password):
        raise BadRequestError("رمز عبور فعلی اشتباه است")

    user.hashed_password = hash_password(new_password)
    user.must_change_password = False
    await _revoke_all_sessions(db, user)
    await db.flush()

    access_token = create_access_token(_token_payload(user))
    refresh_token = create_refresh_token(_token_payload(user))
    db.add(
        RefreshToken(
            id=uuid.uuid4(),
            user_id=user.id,
            org_id=user.org_id,
            token_hash=hash_token(refresh_token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
            created_at=datetime.now(timezone.utc),
        )
    )
    await db.commit()
    return _build_token_response(user, access_token, refresh_token)


async def admin_reset_password(db: AsyncSession, user: User) -> str:
    """
    Reset اجباری رمز توسط ادمین (Manager+) — بدون دانستن رمز قبلی.

    یک رمز موقت تصادفی می‌سازد، آن را روی کاربر ست می‌کند، همه‌ی
    session های فعال کاربر را باطل می‌کند (خروج اجباری از همه دستگاه‌ها)
    و must_change_password=True می‌شود.

    خروجی: رمز موقت به‌صورت plain-text — تنها لحظه‌ای که این رمز در کل
    سیستم به‌صورت خوانا وجود دارد؛ در جایی ذخیره نمی‌شود و فقط در همین
    یک پاسخ API به ادمین بازگردانده می‌شود تا دستی به کاربر بدهد.
    """
    temp_password = generate_temp_password()
    user.hashed_password = hash_password(temp_password)
    user.must_change_password = True
    await _revoke_all_sessions(db, user)
    await db.commit()
    return temp_password


# ─── Profile (GET /me) ──────────────────────────────────────────────────────

async def get_me(db: AsyncSession, user: User) -> dict:
    """پروفایل کامل کاربر لاگین‌شده — شامل نام سازمان/دپارتمان/سمت."""
    from sqlalchemy.orm import joinedload

    result = await db.execute(
        select(User)
        .where(User.id == user.id)
        .options(joinedload(User.department), joinedload(User.position))
    )
    user = result.scalar_one()
    org = await db.get(Organization, user.org_id)
    return {
        "id": str(user.id),
        "org_id": str(user.org_id),
        "org_name": org.name if org else "—",
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "is_active": user.is_active,
        "avatar_url": user.avatar_url,
        "phone": user.phone,
        "department": user.department.name if user.department else None,
        "position": user.position.name if user.position else None,
        "last_login_at": user.last_login_at,
        "must_change_password": user.must_change_password,
    }
