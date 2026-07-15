"""
Talentick — User Service
==========================
Business logic برای مدیریت کاربران (CRUD کامل).

قوانین:
- super_admin: به همه کاربران در همه سازمان‌ها دسترسی دارد
- org_admin/manager: فقط کاربران سازمان خودشان (org scoping در router
  اعمال می‌شود — اینجا فقط org_id به‌عنوان فیلتر/مقدار پاس داده می‌شود)
- هیچ query مستقیم در router نیست
- هرگز پسورد را plain-text ذخیره نکنید — همیشه از hash_password استفاده کنید
"""

from __future__ import annotations

import math
import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.security import hash_password
from app.models.organization import Organization
from app.models.user import User
from app.schemas.user import (
    PaginatedUsers,
    UserCreateRequest,
    UserListItem,
    UserUpdateRequest,
)


def _to_list_item(user: User, org_name: str) -> UserListItem:
    """User ORM → UserListItem — department/position را از relationship می‌خواند (نه ستون مستقیم)."""
    return UserListItem(
        id=str(user.id),
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        department=user.department.name if user.department else None,
        position=user.position.name if user.position else None,
        org_id=str(user.org_id),
        org_name=org_name,
        is_active=user.is_active,
        created_at=user.created_at,
    )


# ─── List (با فیلتر اختیاری org_id — برای org_admin/manager همیشه پر می‌شود) ──

async def list_users(
    db: AsyncSession,
    page: int = 1,
    per_page: int = 20,
    search: str | None = None,
    role: str | None = None,
    org_id: str | None = None,
    dept_id: str | None = None,
    position_id: str | None = None,
    is_active: bool | None = None,
) -> PaginatedUsers:
    """
    لیست کاربران با فیلتر و صفحه‌بندی.

    اگر org_id پاس داده شود فقط کاربران همان سازمان برمی‌گردند —
    این مقدار را router بر اساس نقش کاربر فعلی تعیین می‌کند
    (super_admin می‌تواند None بدهد یعنی همه سازمان‌ها).

    قانون Soft Delete: کاربران غیرفعال (is_active=False) به‌طور پیش‌فرض
    از لیست/جستجو مخفی می‌شوند. برای دیدن آن‌ها باید صریحاً
    is_active=false در query param فرستاده شود.
    """
    if is_active is None:
        is_active = True

    base_q = (
        select(User, Organization.name.label("org_name"))
        .join(Organization, User.org_id == Organization.id)
        .options(joinedload(User.department), joinedload(User.position))
    )

    if search:
        like = f"%{search}%"
        base_q = base_q.where(
            (User.full_name.ilike(like)) | (User.email.ilike(like))
        )
    if role:
        base_q = base_q.where(User.role == role)
    if org_id:
        base_q = base_q.where(User.org_id == uuid.UUID(org_id))
    if dept_id:
        base_q = base_q.where(User.dept_id == uuid.UUID(dept_id))
    if position_id:
        base_q = base_q.where(User.position_id == uuid.UUID(position_id))
    if is_active is not None:
        base_q = base_q.where(User.is_active.is_(is_active))

    count_q = select(func.count()).select_from(base_q.subquery())
    total: int = await db.scalar(count_q) or 0

    offset = (page - 1) * per_page
    rows = await db.execute(
        base_q.order_by(User.created_at.desc()).offset(offset).limit(per_page)
    )

    items = [_to_list_item(row.User, row.org_name) for row in rows.all()]

    return PaginatedUsers(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=max(1, math.ceil(total / per_page)),
    )


# نگه‌داشته شده برای سازگاری با importهای قدیمی (super_admin/all)
async def list_all_users(
    db: AsyncSession,
    page: int = 1,
    per_page: int = 20,
    search: str | None = None,
    role: str | None = None,
    org_id: str | None = None,
    is_active: bool | None = None,
) -> PaginatedUsers:
    return await list_users(
        db, page=page, per_page=per_page, search=search,
        role=role, org_id=org_id, is_active=is_active,
    )


# ─── Get one ───────────────────────────────────────────────────────────────────

async def get_user(db: AsyncSession, user_id: str) -> User | None:
    """یک کاربر را با id برمی‌گرداند — None اگر نبود یا id نامعتبر بود."""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        return None
    result = await db.execute(
        select(User)
        .where(User.id == uid)
        .options(joinedload(User.department), joinedload(User.position))
    )
    return result.scalar_one_or_none()


async def get_user_with_org(db: AsyncSession, user_id: str) -> tuple[User, str] | None:
    """کاربر به‌همراه نام سازمانش — برای ساخت UserDetail/UserListItem کامل."""
    user = await get_user(db, user_id)
    if not user:
        return None
    org = await db.get(Organization, user.org_id)
    return user, (org.name if org else "—")


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


# ─── Create ────────────────────────────────────────────────────────────────────

class EmailAlreadyExistsError(Exception):
    """ایمیل از قبل در سیستم ثبت شده — یکتا در کل پلتفرم است."""


async def create_user(db: AsyncSession, data: UserCreateRequest) -> User:
    """
    کاربر جدید می‌سازد.

    org_id و role قبل از رسیدن به این تابع باید توسط router اعتبارسنجی
    شده باشند (مثلاً org_admin فقط در org خودش بسازد).
    """
    existing = await get_user_by_email(db, data.email)
    if existing:
        raise EmailAlreadyExistsError(data.email)

    user = User(
        id=uuid.uuid4(),
        org_id=uuid.UUID(data.org_id),
        email=data.email,
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
        role=data.role,
        phone=data.phone,
        dept_id=uuid.UUID(data.dept_id) if data.dept_id else None,
        position_id=uuid.UUID(data.position_id) if data.position_id else None,
        manager_id=uuid.UUID(data.manager_id) if data.manager_id else None,
        is_active=True,
        # رمز را خودِ ادمین انتخاب کرده (نه کاربر) — پس باید هنگام اولین
        # ورود عوض شود تا رمز نزد ادمین «دائمی معتبر» باقی نماند.
        must_change_password=True,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise EmailAlreadyExistsError(data.email) from exc
    await db.commit()

    result = await db.execute(
        select(User)
        .where(User.id == user.id)
        .options(
            joinedload(User.department),
            joinedload(User.position),
        )
    )

    return result.scalar_one()


# ─── Update ────────────────────────────────────────────────────────────────────

async def update_user(db: AsyncSession, user: User, data: UserUpdateRequest) -> User:
    """
    ویرایش partial کاربر.

    اعتبارسنجی role/org (مثلاً org_admin نمی‌تواند role را super_admin کند)
    در router انجام می‌شود — این تابع فقط مقادیر را اعمال می‌کند.

    فیلدهای UUID (dept_id/position_id/manager_id) دستی پردازش می‌شوند:
    - رشته خالی "" → پاک کردن (NULL)
    - رشته UUID معتبر → تنظیم
    - ارسال‌نشدن (unset) → بدون تغییر
    """
    if data.email is not None and data.email != user.email:
        existing = await get_user_by_email(db, data.email)
        if existing and str(existing.id) != str(user.id):
            raise EmailAlreadyExistsError(data.email)

    payload = data.model_dump(exclude_unset=True)
    uuid_fields = {"dept_id", "position_id", "manager_id"}

    for field, value in payload.items():
        if field in uuid_fields:
            setattr(user, field, uuid.UUID(value) if value else None)
        elif value is not None:
            setattr(user, field, value)

    await db.commit()

    result = await db.execute(
        select(User)
        .where(User.id == user.id)
        .options(
            joinedload(User.department),
            joinedload(User.position),
        )
    )

    return result.scalar_one()


# ─── Delete (Soft Delete) ────────────────────────────────────────────────────

async def delete_user(db: AsyncSession, user: User) -> None:
    """
    غیرفعال‌سازی کاربر (Soft Delete) — هیچ رکوردی از دیتابیس پاک نمی‌شود.

    دلیل: کاربر ممکن است سابقه‌ی مرتبط (quiz_attempts، content progress،
    onboarding enrollments و ...) داشته باشد که با حذف فیزیکی از بین
    می‌رفت. به‌جای آن is_active=False می‌شود و کاربر می‌تواند بعداً از
    طریق toggle-active دوباره فعال شود.

    توجه: اگر کاربر از قبل غیرفعال بوده، این عملیات idempotent است.
    """
    user.is_active = False
    await db.commit()


# ─── Toggle active ──────────────────────────────────────────────────────────────

async def toggle_user_active(db: AsyncSession, user: User) -> User:
    """وضعیت فعال/غیرفعال کاربر را toggle می‌کند."""
    user.is_active = not user.is_active
    await db.commit()
    await db.refresh(user)
    return user