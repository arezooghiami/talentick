"""
Talentick — Content Schemas
=============================
Content (کانتینر: course/article/podcast/book) + ContentItem (آیتم داخلی).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

CONTENT_TYPES = ("course", "article", "podcast", "book")
ITEM_TYPES = ("text", "video", "pdf", "image", "link", "file", "quiz_ref")
CONTENT_STATUSES = ("draft", "published", "archived")
CONTENT_LEVELS = ("beginner", "intermediate", "advanced")


# ─── ContentItem ───────────────────────────────────────────────────────────

class ContentItemCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=500)
    type: str = Field(..., description="text | video | pdf | image | link | file | quiz_ref")
    body: Optional[str] = None
    media_url: Optional[str] = None
    quiz_id: Optional[str] = None
    duration_min: Optional[int] = Field(None, ge=0)
    order_index: int = 0
    is_free: bool = True


class ContentItemUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=500)
    type: Optional[str] = None
    body: Optional[str] = None
    media_url: Optional[str] = None
    quiz_id: Optional[str] = None
    duration_min: Optional[int] = Field(None, ge=0)
    order_index: Optional[int] = None
    is_free: Optional[bool] = None


class ContentItemResponse(BaseModel):
    id: str
    content_id: str
    title: str
    type: str
    body: Optional[str] = None
    media_url: Optional[str] = None
    quiz_id: Optional[str] = None
    duration_min: Optional[int] = None
    order_index: int
    is_free: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Content ────────────────────────────────────────────────────────────────

class ContentCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=500)
    type: str = Field(..., description="course | article | podcast | book")
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    author: Optional[str] = None
    instructor_name: Optional[str] = None
    instructor_avatar_url: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    status: str = Field("draft", description="draft | published | archived")
    level: Optional[str] = None
    total_duration_min: Optional[int] = Field(None, ge=0)
    is_featured: bool = False
    meta: dict = Field(default_factory=dict)
    org_id: Optional[str] = None  # فقط super_admin — در router enforce می‌شود


class ContentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=500)
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    author: Optional[str] = None
    instructor_name: Optional[str] = None
    instructor_avatar_url: Optional[str] = None
    tags: Optional[list[str]] = None
    status: Optional[str] = None
    level: Optional[str] = None
    total_duration_min: Optional[int] = Field(None, ge=0)
    is_featured: Optional[bool] = None
    meta: Optional[dict] = None


class ContentResponse(BaseModel):
    id: str
    org_id: str
    title: str
    type: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    author: Optional[str] = None
    instructor_name: Optional[str] = None
    instructor_avatar_url: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    status: str
    level: Optional[str] = None
    total_duration_min: Optional[int] = None
    total_items_count: int
    is_featured: bool
    created_by: Optional[str] = None
    created_by_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ContentDetailResponse(ContentResponse):
    items: list[ContentItemResponse] = Field(default_factory=list)


class ContentListResponse(BaseModel):
    items: list[ContentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class UploadResponse(BaseModel):
    url: str
    filename: Optional[str] = None
    size: int
    content_type: Optional[str] = None
