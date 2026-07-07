"""
Talentick — Users Router
===========================
CRUD کامل کاربران با رعایت سلسله‌مراتب نقش و Org Isolation.

سطوح دسترسی:
- GET  /api/users/me                  → پروفایل خودم (هر کاربر فعال)
- GET  /api/users/all                 → لیست همه کاربران همه سازمان‌ها — فقط super_admin
- GET  /api/users/                    → لیست کاربران سازمانِ خودِ کاربر — manager به بالا
                                         (super_admin می‌تواند با org_id فیلتر کند یا همه را ببیند)
- GET  /api/users/{id}                → جزئیات یک کاربر — manager به بالا + org isolation
- POST /api/users/                    → ساخت کاربر جدید — فقط org_admin به بالا
- PATCH /api/users/{id}               → ویرایش کاربر — manager به بالا + org isolation
- DELETE /api/users/{id}              → غیرفعال‌سازی کاربر (Soft Delete —
                                         is_active=False، هیچ رکوردی پاک نمی‌شود)
                                         — manager به بالا + org isolation
- PATCH /api/users/{id}/toggle-active → فعال/غیرفعال — manager به بالا + org isolation
                                         (برای بازگرداندن کاربر soft-delete‌شده هم استفاده می‌شود)

قانون طلایی Org Isolation:
هر کاربری که super_admin نیست، فقط می‌تواند کاربران سازمان خودش را
ببیند/بسازد/ویرایش/حذف کند. این بررسی همیشه با _enforce_org_scope انجام می‌شود.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import CurrentUser, Manager, OrgAdmin, require_active
from app.models.user import User
from app.schemas.user import (
    PaginatedUsers,
    UserCreateRequest,
    UserDetail,
    UserUpdateRequest,
)
from app.services import user_service

router = APIRouter(
    prefix="/api/users",
    tags=["Users"],
)


# ─── Helpers ────────────────────────────────────────────────────────────────────

def _enforce_org_scope(current_user: User, target_org_id) -> None:
    """
    super_admin استثنا است. هر نقش دیگر فقط به سازمان خودش دسترسی دارد.
    در صورت نقض → 403.
    """
    if current_user.role == "super_admin":
        return
    if str(current_user.org_id) != str(target_org_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="دسترسی به کاربران این سازمان مجاز نیست",
        )


async def _to_detail(db: AsyncSession, user: User) -> UserDetail:
    manager_name = None
    if user.manager_id:
        manager = await user_service.get_user(db, str(user.manager_id))
        manager_name = manager.full_name if manager else None
    return UserDetail(
        id=str(user.id),
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        department=user.department.name if user.department else None,
        dept_id=str(user.dept_id) if user.dept_id else None,
        position=user.position.name if user.position else None,
        position_id=str(user.position_id) if user.position_id else None,
        manager_id=str(user.manager_id) if user.manager_id else None,
        manager_name=manager_name,
        phone=user.phone,
        org_id=str(user.org_id),
        is_active=user.is_active,
        created_at=user.created_at,
    )


async def _validate_org_refs(db: AsyncSession, org_id, dept_id: str | None, position_id: str | None, manager_id: str | None) -> None:
    """
    تضمین می‌کند dept_id/position_id/manager_id داده‌شده واقعاً متعلق به
    همان سازمان هستند — جلوگیری از اتصال کاربر یک سازمان به واحد/پست/
    مدیرِ سازمان دیگر.
    """
    from app.services import department_service, position_service

    if dept_id:
        dept = await department_service.get_department(db, dept_id)
        if not dept or str(dept.org_id) != str(org_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "واحد سازمانی انتخاب‌شده معتبر نیست")
    if position_id:
        pos = await position_service.get_position(db, position_id)
        if not pos or str(pos.org_id) != str(org_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "پست سازمانی انتخاب‌شده معتبر نیست")
    if manager_id:
        mgr = await user_service.get_user(db, manager_id)
        if not mgr or str(mgr.org_id) != str(org_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "مدیر مستقیم انتخاب‌شده معتبر نیست")


# ─── /me — پروفایل کاربر فعلی ────────────────────────────────────────────────

@router.get("/me", response_model=UserDetail, summary="پروفایل کاربر فعلی")
async def get_my_profile(
    current_user: Annotated[User, Depends(require_active)],
    db: AsyncSession = Depends(get_db),
) -> UserDetail:
    return await _to_detail(db, current_user)


# ─── /all — لیست همه کاربران (فقط super_admin) ───────────────────────────────

@router.get(
    "/all",
    response_model=PaginatedUsers,
    summary="لیست همه کاربران پلتفرم (فقط super_admin)",
)
async def list_all_users(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    role: str | None = Query(None),
    org_id: str | None = Query(None),
    is_active: bool | None = Query(
        None, description="پیش‌فرض فقط کاربران فعال. برای دیدن غیرفعال‌ها صراحتاً false بدهید."
    ),
) -> PaginatedUsers:
    if current_user.role != "super_admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی محدود است — نقش مورد نیاز: super_admin")
    return await user_service.list_users(
        db, page=page, per_page=per_page, search=search,
        role=role, org_id=org_id, is_active=is_active,
    )


# ─── / — لیست کاربران سازمان خودِ کاربر (org_admin / manager / super_admin) ───

@router.get(
    "/",
    response_model=PaginatedUsers,
    summary="لیست کاربران سازمان (org-scoped)",
    description="""
    org_admin و manager فقط کاربران سازمان خودشان را می‌بینند.
    super_admin می‌تواند با پارامتر org_id فیلتر کند یا خالی بگذارد (همه سازمان‌ها).
    """,
)
async def list_org_users(
    current_user: Manager,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    role: str | None = Query(None),
    org_id: str | None = Query(None, description="فقط برای super_admin معتبر است"),
    is_active: bool | None = Query(
        None, description="پیش‌فرض فقط کاربران فعال. برای دیدن غیرفعال‌ها (soft-deleted) صراحتاً false بدهید."
    ),
) -> PaginatedUsers:
    scoped_org_id = org_id if current_user.role == "super_admin" else str(current_user.org_id)
    return await user_service.list_users(
        db, page=page, per_page=per_page, search=search,
        role=role, org_id=scoped_org_id, is_active=is_active,
    )


# ─── GET /{id} — جزئیات یک کاربر ──────────────────────────────────────────────

@router.get("/{user_id}", response_model=UserDetail, summary="جزئیات یک کاربر")
async def get_user(
    user_id: str,
    current_user: Manager,
    db: AsyncSession = Depends(get_db),
) -> UserDetail:
    found = await user_service.get_user_with_org(db, user_id)
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کاربر یافت نشد")
    user, org_name = found
    _enforce_org_scope(current_user, user.org_id)
    return await _to_detail(db, user)


# ─── POST / — ساخت کاربر جدید (org_admin به بالا) ─────────────────────────────

@router.post(
    "/",
    response_model=UserDetail,
    status_code=status.HTTP_201_CREATED,
    summary="ساخت کاربر جدید",
    description="""
    **دسترسی:** super_admin، org_admin (manager اجازه ساخت کاربر ندارد).

    - super_admin: می‌تواند در هر سازمانی، با هر نقشی کاربر بسازد.
    - org_admin: فقط در سازمان خودش، و نمی‌تواند نقش super_admin بسازد.
    """,
)
async def create_user(
    body: UserCreateRequest,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
) -> UserDetail:
    if current_user.role != "super_admin":
        # org_admin: فقط در سازمان خودش، فقط نقش‌های غیر super_admin
        if body.org_id != str(current_user.org_id):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "فقط می‌توانید در سازمان خودتان کاربر بسازید")
        if body.role == "super_admin":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "اجازه ساخت کاربر با نقش super_admin را ندارید")

    await _validate_org_refs(db, body.org_id, body.dept_id, body.position_id, body.manager_id)

    try:
        user = await user_service.create_user(db, body)
    except user_service.EmailAlreadyExistsError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این ایمیل قبلاً ثبت شده است")

    return await _to_detail(db, user)


# ─── PATCH /{id} — ویرایش کاربر ───────────────────────────────────────────────

@router.patch("/{user_id}", response_model=UserDetail, summary="ویرایش کاربر")
async def update_user(
    user_id: str,
    body: UserUpdateRequest,
    current_user: Manager,
    db: AsyncSession = Depends(get_db),
) -> UserDetail:
    user = await user_service.get_user(db, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کاربر یافت نشد")

    _enforce_org_scope(current_user, user.org_id)

    if current_user.role != "super_admin" and body.role == "super_admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "اجازه تنظیم نقش super_admin را ندارید")

    if str(user.id) == body.manager_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "کاربر نمی‌تواند مدیر مستقیم خودش باشد")

    await _validate_org_refs(db, user.org_id, body.dept_id, body.position_id, body.manager_id)

    try:
        updated = await user_service.update_user(db, user, body)
    except user_service.EmailAlreadyExistsError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این ایمیل قبلاً ثبت شده است")

    return await _to_detail(db, updated)


# ─── DELETE /{id} — حذف کاربر ─────────────────────────────────────────────────

@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="غیرفعال‌سازی کاربر (Soft Delete)",
    description="""
    کاربر را غیرفعال می‌کند (is_active=False) — هیچ رکوردی از دیتابیس پاک
    نمی‌شود. کاربر غیرفعال‌شده به‌طور پیش‌فرض از لیست‌ها و جستجوها مخفی
    می‌شود، اما سابقه‌ی او (محتوا، آزمون، onboarding) دست‌نخورده باقی می‌ماند
    و از طریق `PATCH /{id}/toggle-active` قابل بازگردانی است.
    """,
)
async def delete_user(
    user_id: str,
    current_user: Manager,
    db: AsyncSession = Depends(get_db),
) -> None:
    user = await user_service.get_user(db, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کاربر یافت نشد")

    _enforce_org_scope(current_user, user.org_id)

    if str(user.id) == str(current_user.id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نمی‌توانید حساب خودتان را حذف کنید")

    await user_service.delete_user(db, user)


# ─── PATCH /{id}/toggle-active ───────────────────────────────────────────────

@router.patch("/{user_id}/toggle-active", summary="فعال/غیرفعال کردن کاربر")
async def toggle_user_active(
    user_id: str,
    current_user: Manager,
    db: AsyncSession = Depends(get_db),
) -> dict:
    user = await user_service.get_user(db, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کاربر یافت نشد")

    _enforce_org_scope(current_user, user.org_id)

    if str(user.id) == str(current_user.id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نمی‌توانید وضعیت حساب خودتان را تغییر دهید")

    updated = await user_service.toggle_user_active(db, user)
    return {
        "id": str(updated.id),
        "is_active": updated.is_active,
        "message": "کاربر فعال شد" if updated.is_active else "کاربر غیرفعال شد",
    }