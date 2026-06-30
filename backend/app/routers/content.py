"""
Talentick — Content Router
=============================
مدیریت محتوای سازمانی (course/article/podcast/book) — برای ادمین سازمان.

Routes:
  GET    /api/contents/                 → لیست محتوا (با فیلتر/جستجو/صفحه‌بندی)
  POST   /api/contents/                 → ساخت محتوا جدید
  GET    /api/contents/{id}             → جزئیات + آیتم‌ها
  PATCH  /api/contents/{id}             → ویرایش
  DELETE /api/contents/{id}             → حذف
  POST   /api/contents/upload           → آپلود فایل/تصویر/ویدیو به MinIO
  POST   /api/contents/{id}/items       → افزودن آیتم به محتوا
  PATCH  /api/contents/items/{item_id}  → ویرایش آیتم
  DELETE /api/contents/items/{item_id}  → حذف آیتم

دسترسی: ساخت/ویرایش/حذف فقط OrgAdmin به بالا (سازمان خودشان).
مشاهده: هر کاربر فعال سازمان (Employee به بالا) — برای صفحه اول کاربران در آینده.
"""

from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import upload_file
from app.database import get_db
from app.dependencies import Employee, OrgAdmin
from app.models.content import Content
from app.models.user import User
from app.schemas.content import (
    CONTENT_STATUSES,
    CONTENT_TYPES,
    ITEM_TYPES,
    ContentCreate,
    ContentDetailResponse,
    ContentItemCreate,
    ContentItemResponse,
    ContentItemUpdate,
    ContentListResponse,
    ContentResponse,
    ContentUpdate,
    UploadResponse,
)
from app.services import content_service

router = APIRouter(prefix="/api/contents", tags=["Content"])


# ─── Helpers ──────────────────────────────────────────────────────────────

def _enforce_org_scope(current_user: User, target_org_id: uuid.UUID) -> None:
    if current_user.role == "super_admin":
        return
    if str(current_user.org_id) != str(target_org_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی به این سازمان مجاز نیست")


def _resolve_org_id(current_user: User, org_id: str | None) -> uuid.UUID:
    """super_admin می‌تواند org_id دلخواه بدهد، سایر نقش‌ها محدود به سازمان خودشان هستند."""
    if current_user.role == "super_admin" and org_id:
        try:
            return uuid.UUID(org_id)
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "org_id نامعتبر است")
    if current_user.org_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "org_id الزامی است")
    return current_user.org_id


def _validate_type(value: str) -> None:
    if value not in CONTENT_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"نوع محتوا نامعتبر است — مقادیر مجاز: {', '.join(CONTENT_TYPES)}",
        )


def _validate_status(value: str) -> None:
    if value not in CONTENT_STATUSES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"وضعیت نامعتبر است — مقادیر مجاز: {', '.join(CONTENT_STATUSES)}",
        )


def _validate_item_type(value: str) -> None:
    if value not in ITEM_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"نوع آیتم نامعتبر است — مقادیر مجاز: {', '.join(ITEM_TYPES)}",
        )


async def _get_content_or_404(db: AsyncSession, content_id: str) -> Content:
    content = await content_service.get_content(db, content_id)
    if not content:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "محتوا یافت نشد")
    return content


# ─── Content Routes ─────────────────────────────────────────────────────────

@router.get("/", response_model=ContentListResponse, summary="لیست محتوای سازمان")
async def list_contents(
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    type: str | None = Query(None, description="course | article | podcast | book"),
    status_filter: str | None = Query(None, alias="status"),
    org_id: str | None = Query(None, description="فقط super_admin"),
):
    target_org_id = _resolve_org_id(current_user, org_id)
    if type:
        _validate_type(type)
    if status_filter:
        _validate_status(status_filter)

    # کارمندان عادی فقط محتوای منتشرشده را می‌بینند
    if current_user.role == "employee" and not status_filter:
        status_filter = "published"

    items, total = await content_service.list_contents(
        db, target_org_id, page=page, page_size=page_size,
        search=search, type_filter=type, status_filter=status_filter,
    )
    responses = [await content_service.content_to_response(db, c) for c in items]
    return ContentListResponse(
        items=responses,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
    )


@router.post(
    "/", response_model=ContentDetailResponse, status_code=status.HTTP_201_CREATED,
    summary="ساخت محتوای جدید",
)
async def create_content(
    body: ContentCreate,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    _validate_type(body.type)
    _validate_status(body.status)

    org_id = current_user.org_id
    if current_user.role == "super_admin" and body.org_id:
        org_id = uuid.UUID(body.org_id)
    if org_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "org_id الزامی است")

    content = await content_service.create_content(db, org_id, current_user.id, body)
    return await content_service.content_to_detail(db, content)


@router.get("/{content_id}", response_model=ContentDetailResponse, summary="جزئیات محتوا")
async def get_content(
    content_id: str,
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
):
    content = await _get_content_or_404(db, content_id)
    _enforce_org_scope(current_user, content.org_id)
    if current_user.role == "employee" and content.status != "published":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "محتوا یافت نشد")
    return await content_service.content_to_detail(db, content)


@router.patch("/{content_id}", response_model=ContentDetailResponse, summary="ویرایش محتوا")
async def update_content(
    content_id: str,
    body: ContentUpdate,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    content = await _get_content_or_404(db, content_id)
    _enforce_org_scope(current_user, content.org_id)
    if body.status:
        _validate_status(body.status)
    updated = await content_service.update_content(db, content, body)
    return await content_service.content_to_detail(db, updated)


@router.delete("/{content_id}", status_code=status.HTTP_204_NO_CONTENT, summary="حذف محتوا")
async def delete_content(
    content_id: str,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    content = await _get_content_or_404(db, content_id)
    _enforce_org_scope(current_user, content.org_id)
    await content_service.delete_content(db, content)


# ─── Upload ──────────────────────────────────────────────────────────────

@router.post("/upload", response_model=UploadResponse, summary="آپلود فایل/تصویر/ویدیوی محتوا به MinIO")
async def upload_content_file(
    current_user: OrgAdmin,
    file: UploadFile = File(...),
):
    org_id = current_user.org_id
    if org_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "org_id الزامی است")
    result = await upload_file(file, org_id, subfolder="contents")
    return UploadResponse(**result)


# ─── ContentItem Routes ─────────────────────────────────────────────────────

@router.post(
    "/{content_id}/items", response_model=ContentItemResponse, status_code=status.HTTP_201_CREATED,
    summary="افزودن آیتم به محتوا",
)
async def add_item(
    content_id: str,
    body: ContentItemCreate,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    content = await _get_content_or_404(db, content_id)
    _enforce_org_scope(current_user, content.org_id)
    _validate_item_type(body.type)
    item = await content_service.add_item(db, content, body)
    return content_service.item_to_response(item)


@router.patch("/items/{item_id}", response_model=ContentItemResponse, summary="ویرایش آیتم")
async def update_item(
    item_id: str,
    body: ContentItemUpdate,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    item = await content_service.get_item(db, item_id)
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "آیتم یافت نشد")
    _enforce_org_scope(current_user, item.org_id)
    if body.type:
        _validate_item_type(body.type)
    updated = await content_service.update_item(db, item, body)
    return content_service.item_to_response(updated)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary="حذف آیتم")
async def delete_item(
    item_id: str,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    item = await content_service.get_item(db, item_id)
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "آیتم یافت نشد")
    _enforce_org_scope(current_user, item.org_id)
    await content_service.delete_item(db, item)
