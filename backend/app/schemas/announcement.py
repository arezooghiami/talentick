"""
Talentick — Announcement Schemas
====================================
اطلاعیه‌ی تک‌فایلی (عکس/ویدیو) — خارج از سیستم محتوای آموزشی.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

MEDIA_TYPES = ("image", "video")
ANNOUNCEMENT_TARGET_TYPES = ("department", "role")


# ─── AnnouncementTarget (دسترسی: واحد/نقش) ──────────────────────────────────

class AnnouncementTargetCreate(BaseModel):
    """
    منطق نهایی (در announcement_service.visibility_condition): بدون هیچ
    target = برای کل سازمان. با وجود target، کافیست کاربر با یکی از
    سطرها مطابقت داشته باشد (OR) — هم‌ساختار با document_service.
    """
    target_type: str = Field(..., description="department | role")
    target_id: str = Field(..., min_length=1, description="UUID واحد یا نام نقش")


class AnnouncementTargetResponse(BaseModel):
    id: str
    target_type: str
    target_id: str
    target_label: Optional[str] = None

    model_config = {"from_attributes": True}


# ─── Announcement ────────────────────────────────────────────────────────────

class AnnouncementCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=500)
    description: Optional[str] = None
    media_url: str
    media_type: str = Field(..., description="image | video")
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    is_active: bool = True
    org_id: Optional[str] = Field(None, description="فقط super_admin — در router enforce می‌شود")
    targets: list[AnnouncementTargetCreate] = Field(
        default_factory=list,
        description="قوانین دسترسی — خالی یعنی برای کل سازمان",
    )


class AnnouncementUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=500)
    description: Optional[str] = None
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    is_active: Optional[bool] = None
    targets: Optional[list[AnnouncementTargetCreate]] = Field(
        None,
        description="اگر ارسال شود، جایگزین همه‌ی قوانین قبلی می‌شود. [] یعنی پاک‌کردن (کل سازمان).",
    )


class AnnouncementResponse(BaseModel):
    id: str
    org_id: str
    org_name: Optional[str] = None
    title: str
    description: Optional[str] = None
    media_url: str
    media_type: str
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    is_active: bool
    created_by: Optional[str] = None
    created_by_name: Optional[str] = None
    target_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AnnouncementDetailResponse(AnnouncementResponse):
    targets: list[AnnouncementTargetResponse] = Field(default_factory=list)


class AnnouncementListResponse(BaseModel):
    items: list[AnnouncementResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
