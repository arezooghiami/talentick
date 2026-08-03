"""
Talentick — Gallery Schemas
==============================
گالری (مجموعه عکس) — خارج از سیستم محتوای آموزشی.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ─── GalleryPhoto ────────────────────────────────────────────────────────────

class GalleryPhotoCreate(BaseModel):
    image_url: str
    order_index: int = 0


class GalleryPhotoResponse(BaseModel):
    id: str
    image_url: str
    order_index: int

    model_config = {"from_attributes": True}


# ─── Gallery ─────────────────────────────────────────────────────────────────

class GalleryCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=500)
    description: Optional[str] = None
    cover_image_url: Optional[str] = None
    is_active: bool = True
    org_id: Optional[str] = Field(None, description="فقط super_admin — در router enforce می‌شود")
    is_public: bool = Field(
        False,
        description="گالری Public/General (بدون سازمان) — فقط super_admin مجاز است",
    )
    photos: list[GalleryPhotoCreate] = Field(default_factory=list)


class GalleryUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=500)
    description: Optional[str] = None
    cover_image_url: Optional[str] = None
    is_active: Optional[bool] = None
    photos: Optional[list[GalleryPhotoCreate]] = Field(
        None,
        description="اگر ارسال شود، جایگزین همه‌ی عکس‌های قبلی می‌شود. [] یعنی پاک‌کردن همه.",
    )


class GalleryResponse(BaseModel):
    id: str
    org_id: Optional[str] = None
    org_name: Optional[str] = None
    title: str
    description: Optional[str] = None
    cover_image_url: Optional[str] = None
    is_active: bool
    created_by: Optional[str] = None
    created_by_name: Optional[str] = None
    photo_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GalleryDetailResponse(GalleryResponse):
    photos: list[GalleryPhotoResponse] = Field(default_factory=list)


class GalleryListResponse(BaseModel):
    items: list[GalleryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
