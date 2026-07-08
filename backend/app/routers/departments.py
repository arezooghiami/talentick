"""
Talentick — Departments Router
=================================
ساختار سازمانی (چارت واحدها) — CRUD کامل + endpoint چارت درختی.

سطح دسترسی: manager به بالا (manager, org_admin, super_admin) با Org Isolation.
manager طبق سیاست فعلی پروژه روی محتوا/آزمون کنترل کامل دارد، بنابراین
مدیریت ساختار سازمانی (واحدها/پست‌ها) هم در همین سطح قرار گرفته است.

Routes:
  GET    /api/departments/         → لیست مسطح واحدهای سازمان
  GET    /api/departments/tree     → چارت سازمانی درختی
  POST   /api/departments/         → ساخت واحد جدید
  GET    /api/departments/{id}     → جزئیات
  PATCH  /api/departments/{id}     → ویرایش
  DELETE /api/departments/{id}     → حذف (زیرواحدها/کاربران SET NULL می‌شوند)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import Manager
from app.models.user import User
from app.schemas.department import (
    DepartmentCreate,
    DepartmentResponse,
    DepartmentTreeNode,
    DepartmentUpdate,
)
from app.services import department_service

router = APIRouter(prefix="/api/departments", tags=["Departments"])


def _enforce_org_scope(current_user: User, target_org_id) -> None:
    if current_user.role == "super_admin":
        return
    if str(current_user.org_id) != str(target_org_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی به این سازمان مجاز نیست")


def _resolve_org_id(current_user: User, org_id: str | None) -> uuid.UUID:
    """
    تعیین org_id مرجع برای GET های لیستی.
    super_admin می‌تواند org_id دلخواه بدهد (برای مدیریت سازمان دیگران)،
    سایر نقش‌ها همیشه محدود به سازمان خودشان هستند.
    """
    if current_user.role == "super_admin" and org_id:
        try:
            return uuid.UUID(org_id)
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "org_id نامعتبر است")
    if current_user.org_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "org_id الزامی است")
    return current_user.org_id


@router.get(
    "/", response_model=list[DepartmentResponse], summary="لیست واحدهای سازمان",
    description="لیست مسطح (flat) تمام دپارتمان‌های سازمان — برای چارت درختی از `GET /api/departments/tree` استفاده کنید. **دسترسی:** manager به بالا.",
)
async def list_departments(
    current_user: Manager,
    db: AsyncSession = Depends(get_db),
    org_id: str | None = Query(None, description="فقط super_admin — مدیریت سازمان دلخواه"),
):
    target_org_id = _resolve_org_id(current_user, org_id)
    return await department_service.list_departments(db, target_org_id)


@router.get(
    "/tree", response_model=list[DepartmentTreeNode], summary="چارت سازمانی درختی",
    description="ساختار درختی کامل دپارتمان‌ها (parent → children) برای رندر چارت سازمانی در فرانت — هر گره شامل تعداد کاربران و نام مدیر واحد. **دسترسی:** manager به بالا.",
)
async def get_department_tree(
    current_user: Manager,
    db: AsyncSession = Depends(get_db),
    org_id: str | None = Query(None, description="فقط super_admin — مدیریت سازمان دلخواه"),
):
    target_org_id = _resolve_org_id(current_user, org_id)
    return await department_service.build_tree(db, target_org_id)


@router.post(
    "/", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED, summary="ساخت واحد جدید",
    description="ساخت دپارتمان جدید — با `parent_id` اختیاری برای ساخت زیرمجموعه. **دسترسی:** manager به بالا (سازمان خودشان).",
    responses={400: {"description": "واحد مادر (parent_id) معتبر نیست"}},
)
async def create_department(
    body: DepartmentCreate,
    current_user: Manager,
    db: AsyncSession = Depends(get_db),
):
    org_id = current_user.org_id
    if current_user.role == "super_admin" and body.org_id:
        org_id = uuid.UUID(body.org_id)

    if body.parent_id:
        parent = await department_service.get_department(db, body.parent_id)
        if not parent or str(parent.org_id) != str(org_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "واحد مادر معتبر نیست")

    dept = await department_service.create_department(db, org_id, body)
    return await department_service._to_response(db, dept)


@router.get(
    "/{dept_id}", response_model=DepartmentResponse, summary="جزئیات واحد",
    description="جزئیات یک دپارتمان با شناسه‌ی آن. **دسترسی:** manager به بالا (فقط سازمان خودشان — super_admin استثناست).",
    responses={403: {"description": "دسترسی به این سازمان مجاز نیست"}, 404: {"description": "واحد یافت نشد"}},
)
async def get_department(
    dept_id: str,
    current_user: Manager,
    db: AsyncSession = Depends(get_db),
):
    dept = await department_service.get_department(db, dept_id)
    if not dept:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "واحد یافت نشد")
    _enforce_org_scope(current_user, dept.org_id)
    return await department_service._to_response(db, dept)


@router.patch(
    "/{dept_id}", response_model=DepartmentResponse, summary="ویرایش واحد",
    description="ویرایش partial یک دپارتمان — نام، توضیحات، parent_id، manager_id، ترتیب نمایش، وضعیت. **دسترسی:** manager به بالا (سازمان خودشان).",
    responses={
        400: {"description": "واحد مادر معتبر نیست یا واحد نمی‌تواند مادر خودش باشد"},
        403: {"description": "دسترسی به این سازمان مجاز نیست"},
        404: {"description": "واحد یافت نشد"},
    },
)
async def update_department(
    dept_id: str,
    body: DepartmentUpdate,
    current_user: Manager,
    db: AsyncSession = Depends(get_db),
):
    dept = await department_service.get_department(db, dept_id)
    if not dept:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "واحد یافت نشد")
    _enforce_org_scope(current_user, dept.org_id)

    if body.parent_id:
        if body.parent_id == dept_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "یک واحد نمی‌تواند مادر خودش باشد")
        parent = await department_service.get_department(db, body.parent_id)
        if not parent or str(parent.org_id) != str(dept.org_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "واحد مادر معتبر نیست")

    updated = await department_service.update_department(db, dept, body)
    return await department_service._to_response(db, updated)


@router.delete(
    "/{dept_id}", status_code=status.HTTP_204_NO_CONTENT, summary="حذف واحد",
    description="حذف دپارتمان. زیرواحدها و کاربران وابسته حذف نمی‌شوند — فقط `dept_id`/`parent_id` آن‌ها روی NULL تنظیم می‌شود (ondelete=SET NULL). **دسترسی:** manager به بالا (سازمان خودشان).",
    responses={403: {"description": "دسترسی به این سازمان مجاز نیست"}, 404: {"description": "واحد یافت نشد"}},
)
async def delete_department(
    dept_id: str,
    current_user: Manager,
    db: AsyncSession = Depends(get_db),
):
    dept = await department_service.get_department(db, dept_id)
    if not dept:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "واحد یافت نشد")
    _enforce_org_scope(current_user, dept.org_id)
    await department_service.delete_department(db, dept)