"""
Talentick — Gallery Router (Admin)
=====================================
گالری (مجموعه عکس) — خارج از سیستم محتوای آموزشی.

Routes:
  GET    /api/galleries/          → لیست گالری‌های سازمان (مدیریتی)
  POST   /api/galleries/upload    → آپلود عکس به MinIO
  POST   /api/galleries/          → ثبت گالری جدید
  GET    /api/galleries/{id}      → جزئیات
  PATCH  /api/galleries/{id}      → ویرایش
  DELETE /api/galleries/{id}      → حذف

دسترسی: مدیریت (ساخت/ویرایش/حذف/آپلود) org_admin به بالا — هم‌راستا با
announcements.py. تعیین گالری Public/General فقط مجاز برای super_admin.

super_admin: می‌تواند org_id بدهد (لیست یک سازمان خاص) یا ندهد (لیست همه‌ی
سازمان‌ها) — برای ساخت/ویرایش همیشه یک org_id مشخص لازم است، مگر اینکه
is_public=true باشد.
"""

from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import upload_file
from app.database import get_db
from app.dependencies import OrgAdmin
from app.dependencies import enforce_org_scope as _enforce_org_scope
from app.models.user import User
from app.schemas.content import UploadResponse
from app.schemas.gallery import (
    GalleryCreate,
    GalleryDetailResponse,
    GalleryListResponse,
    GalleryUpdate,
)
from app.services import gallery_service

router = APIRouter(prefix="/api/galleries", tags=["Gallery"])

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}


def _resolve_org_id(current_user: User, org_id: str | None) -> uuid.UUID | None:
    """
    super_admin: با org_id فیلتر می‌کند، یا اگر ندهد None برمی‌گردد (یعنی
    مشاهده‌ی گالری‌های همه سازمان‌ها). سایر نقش‌ها همیشه محدود به
    سازمان خودشان. هم‌راستا با announcements._resolve_org_id.
    """
    if current_user.role == "super_admin":
        if org_id:
            try:
                return uuid.UUID(org_id)
            except ValueError:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "org_id نامعتبر است")
        return None
    if current_user.org_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "org_id الزامی است")
    return current_user.org_id


def _resolve_required_org_id(current_user: User, org_id: str | None) -> uuid.UUID:
    """برای ساخت/آپلود که یک org_id مشخص (نه None) لازم دارند."""
    resolved = _resolve_org_id(current_user, org_id)
    if resolved is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "org_id الزامی است")
    return resolved


@router.get("/", response_model=GalleryListResponse, summary="لیست گالری‌های سازمان (مدیریتی)")
async def list_galleries(
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    org_id: str | None = Query(None, description="فقط super_admin — خالی = همه سازمان‌ها"),
):
    target_org_id = _resolve_org_id(current_user, org_id)
    items, total = await gallery_service.list_galleries(
        db, target_org_id, page=page, page_size=page_size, search=search,
    )
    responses = [await gallery_service.gallery_to_response(db, g) for g in items]
    return GalleryListResponse(
        items=responses, total=total, page=page, page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
    )


@router.post("/upload", response_model=UploadResponse, summary="آپلود عکس گالری به MinIO")
async def upload_gallery_image(
    current_user: OrgAdmin,
    file: UploadFile = File(...),
    org_id: str | None = Query(
        None,
        description="فقط super_admin — آپلود برای سازمان دلخواه؛ خالی از سمت super_admin یعنی گالری Public",
    ),
):
    # برای super_admin، org_id=None مجاز است (یعنی گالری Public) — برخلاف
    # _resolve_required_org_id که همیشه یک سازمان مشخص می‌خواهد. سایر
    # نقش‌ها همچنان مجبورند سازمان خودشان را داشته باشند (در _resolve_org_id).
    target_org_id = _resolve_org_id(current_user, org_id)
    ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"فرمت فایل مجاز نیست — فقط عکس: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}",
        )
    result = await upload_file(file, target_org_id, subfolder="galleries")
    return UploadResponse(**result)


@router.post(
    "/", response_model=GalleryDetailResponse, status_code=status.HTTP_201_CREATED,
    summary="ثبت گالری جدید",
)
async def create_gallery(
    body: GalleryCreate,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    if body.is_public:
        if current_user.role != "super_admin":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "فقط super_admin می‌تواند گالری Public بسازد")
        org_id = None
    else:
        org_id = _resolve_required_org_id(current_user, body.org_id)
    gallery = await gallery_service.create_gallery(db, org_id, current_user.id, body)
    return await gallery_service.gallery_to_detail(db, gallery)


@router.get("/{gallery_id}", response_model=GalleryDetailResponse, summary="جزئیات گالری")
async def get_gallery(
    gallery_id: str,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    gallery = await gallery_service.get_gallery(db, gallery_id)
    if not gallery:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "گالری یافت نشد")
    _enforce_org_scope(current_user, gallery.org_id)
    return await gallery_service.gallery_to_detail(db, gallery)


@router.patch("/{gallery_id}", response_model=GalleryDetailResponse, summary="ویرایش گالری")
async def update_gallery(
    gallery_id: str,
    body: GalleryUpdate,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    gallery = await gallery_service.get_gallery(db, gallery_id)
    if not gallery:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "گالری یافت نشد")
    _enforce_org_scope(current_user, gallery.org_id)
    updated = await gallery_service.update_gallery(db, gallery, body)
    return await gallery_service.gallery_to_detail(db, updated)


@router.delete("/{gallery_id}", status_code=status.HTTP_204_NO_CONTENT, summary="حذف گالری")
async def delete_gallery(
    gallery_id: str,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    gallery = await gallery_service.get_gallery(db, gallery_id)
    if not gallery:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "گالری یافت نشد")
    _enforce_org_scope(current_user, gallery.org_id)
    await gallery_service.delete_gallery(db, gallery)
