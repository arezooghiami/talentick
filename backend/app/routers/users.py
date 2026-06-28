"""
Talentick — Users Router
super_admin: همه کاربران همه سازمان‌ها
org_admin: فقط کاربران سازمان خودش
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import CurrentUser, OrgAdmin, SuperAdmin
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services import user_service

router = APIRouter()


@router.get("/", response_model=list[UserResponse])
async def list_users(
    current_user: CurrentUser,
    org_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role == "super_admin":
        return await user_service.list_users(db, org_id=org_id)
    # org_admin فقط کاربران سازمان خودش را می‌بیند
    if current_user.role in ("org_admin", "manager"):
        return await user_service.list_users(db, org_id=current_user.org_id)
    raise HTTPException(status_code=403, detail="دسترسی ندارید")


@router.post("/", response_model=UserResponse, status_code=201)
async def create_user(
    body: UserCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    # super_admin هر org_id‌ای می‌تواند بدهد
    # org_admin فقط سازمان خودش
    if current_user.role != "super_admin":
        if body.org_id != current_user.org_id:
            raise HTTPException(status_code=403, detail="فقط برای سازمان خودتان")
        if body.role == "super_admin":
            raise HTTPException(status_code=403, detail="نمی‌توانید super_admin بسازید")

    existing = await user_service.get_by_email(db, body.email)
    if existing:
        raise HTTPException(status_code=400, detail="این ایمیل قبلاً ثبت شده است")
    return await user_service.create_user(db, body)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    user = await user_service.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد")
    if current_user.role != "super_admin" and user.org_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="دسترسی ندارید")
    return user


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    user = await user_service.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد")
    if current_user.role != "super_admin" and user.org_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="دسترسی ندارید")
    return await user_service.update_user(db, user, body)


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    user = await user_service.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد")
    if current_user.role != "super_admin" and user.org_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="دسترسی ندارید")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="نمی‌توانید حساب خودتان را حذف کنید")
    await user_service.delete_user(db, user)
