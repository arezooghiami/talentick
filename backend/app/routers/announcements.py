"""
Talentick — Announcements Router (Admin)
============================================
اطلاعیه‌ی تک‌فایلی (عکس/ویدیو) — خارج از سیستم محتوای آموزشی، برای
اطلاع‌رسانی سریع در صفحه‌ی خانه‌ی کارمند.

Routes:
  GET    /api/announcements/          → لیست اطلاعیه‌های سازمان (مدیریتی)
  POST   /api/announcements/upload    → آپلود عکس/ویدیو به MinIO
  POST   /api/announcements/          → ثبت اطلاعیه جدید
  GET    /api/announcements/{id}      → جزئیات
  PATCH  /api/announcements/{id}      → ویرایش
  DELETE /api/announcements/{id}      → حذف

مشاهده‌ی اطلاعیه‌های فعال برای کارمندان از routers/me.py
(GET /api/me/announcements) است — آنجا هم بازه‌ی نمایش (starts_at/ends_at)
و هم Permission Engine (announcement_service.visibility_condition) اعمال
می‌شود.

دسترسی: مدیریت (ساخت/ویرایش/حذف/آپلود) فقط org_admin به بالا — بر خلاف
کتابخانه‌ی اسناد (manager به بالا)، چون اطلاعیه یک کانال رسمی ارتباطی
سازمان است، هم‌راستا با content.py.

super_admin: مثل content.py می‌تواند org_id بدهد (لیست یک سازمان خاص) یا
ندهد (لیست همه‌ی سازمان‌ها) — برای ساخت/ویرایش همیشه یک org_id مشخص لازم است.
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
from app.schemas.announcement import (
    AnnouncementCreate,
    AnnouncementDetailResponse,
    AnnouncementListResponse,
    AnnouncementUpdate,
)
from app.schemas.content import UploadResponse
from app.services import announcement_service

router = APIRouter(prefix="/api/announcements", tags=["Announcements"])

ALLOWED_MEDIA_EXTENSIONS = {
    "jpg", "jpeg", "png", "webp", "gif",
    "mp4", "webm", "mov",
}


def _resolve_org_id(current_user: User, org_id: str | None) -> uuid.UUID | None:
    """
    super_admin: با org_id فیلتر می‌کند، یا اگر ندهد None برمی‌گردد (یعنی
    مشاهده‌ی اطلاعیه‌های همه سازمان‌ها). سایر نقش‌ها همیشه محدود به
    سازمان خودشان. هم‌راستا با content._resolve_org_id.
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


@router.get("/", response_model=AnnouncementListResponse, summary="لیست اطلاعیه‌های سازمان (مدیریتی)")
async def list_announcements(
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    org_id: str | None = Query(None, description="فقط super_admin — خالی = همه سازمان‌ها"),
):
    target_org_id = _resolve_org_id(current_user, org_id)
    items, total = await announcement_service.list_announcements(
        db, target_org_id, page=page, page_size=page_size, search=search,
    )
    responses = [await announcement_service.announcement_to_response(db, a) for a in items]
    return AnnouncementListResponse(
        items=responses, total=total, page=page, page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
    )


@router.post("/upload", response_model=UploadResponse, summary="آپلود عکس/ویدیوی اطلاعیه به MinIO")
async def upload_announcement_file(
    current_user: OrgAdmin,
    file: UploadFile = File(...),
    org_id: str | None = Query(None, description="فقط super_admin — آپلود برای سازمان دلخواه"),
):
    target_org_id = _resolve_required_org_id(current_user, org_id)
    ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    if ext not in ALLOWED_MEDIA_EXTENSIONS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"فرمت فایل مجاز نیست — فقط عکس/ویدیو: {', '.join(sorted(ALLOWED_MEDIA_EXTENSIONS))}",
        )
    result = await upload_file(file, target_org_id, subfolder="announcements")
    return UploadResponse(**result)


@router.post(
    "/", response_model=AnnouncementDetailResponse, status_code=status.HTTP_201_CREATED,
    summary="ثبت اطلاعیه جدید",
)
async def create_announcement(
    body: AnnouncementCreate,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    org_id = _resolve_required_org_id(current_user, body.org_id)
    announcement = await announcement_service.create_announcement(db, org_id, current_user.id, body)
    return await announcement_service.announcement_to_detail(db, announcement)


@router.get("/{announcement_id}", response_model=AnnouncementDetailResponse, summary="جزئیات اطلاعیه")
async def get_announcement(
    announcement_id: str,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    announcement = await announcement_service.get_announcement(db, announcement_id)
    if not announcement:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "اطلاعیه یافت نشد")
    _enforce_org_scope(current_user, announcement.org_id)
    return await announcement_service.announcement_to_detail(db, announcement)


@router.patch("/{announcement_id}", response_model=AnnouncementDetailResponse, summary="ویرایش اطلاعیه")
async def update_announcement(
    announcement_id: str,
    body: AnnouncementUpdate,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    announcement = await announcement_service.get_announcement(db, announcement_id)
    if not announcement:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "اطلاعیه یافت نشد")
    _enforce_org_scope(current_user, announcement.org_id)
    updated = await announcement_service.update_announcement(db, announcement, body)
    return await announcement_service.announcement_to_detail(db, updated)


@router.delete("/{announcement_id}", status_code=status.HTTP_204_NO_CONTENT, summary="حذف اطلاعیه")
async def delete_announcement(
    announcement_id: str,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    announcement = await announcement_service.get_announcement(db, announcement_id)
    if not announcement:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "اطلاعیه یافت نشد")
    _enforce_org_scope(current_user, announcement.org_id)
    await announcement_service.delete_announcement(db, announcement)
