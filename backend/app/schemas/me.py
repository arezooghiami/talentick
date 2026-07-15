"""
Talentick — «محتواهای من» (My Contents) Schemas
===================================================
پاسخ‌های اختصاصی پرتال کاربر — مستقل از schema های پنل ادمین، چون هر
کارت/آیتم باید همراه با پیشرفت شخصی همان کاربر برگردانده شود.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MyContentResponse(BaseModel):
    """یک ردیف در فهرست «محتواهای من» — شامل اطلاعات محتوا + پیشرفت شخصی کاربر."""

    id: str
    title: str
    type: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    author: Optional[str] = None
    instructor_name: Optional[str] = None
    instructor_avatar_url: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    level: Optional[str] = None
    total_duration_min: Optional[int] = None
    total_items_count: int
    is_featured: bool
    created_at: datetime

    # پیشرفت شخصی من
    my_status: str = "not_started"
    my_progress_pct: int = 0
    my_last_item_id: Optional[str] = None
    my_last_viewed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class MyContentItemResponse(BaseModel):
    id: str
    title: str
    type: str
    body: Optional[str] = None
    media_url: Optional[str] = None
    quiz_id: Optional[str] = None
    duration_min: Optional[int] = None
    order_index: int
    is_free: bool

    # پیشرفت شخصی من در این آیتم
    my_status: str = "not_started"
    my_progress_pct: int = 0
    my_last_position: Optional[int] = None

    # قفل ترتیبی — اگر True باشد، آیتم‌های قبلی هنوز کامل نشده‌اند
    is_locked: bool = False

    model_config = {"from_attributes": True}


class MyContentDetailResponse(MyContentResponse):
    items: list[MyContentItemResponse] = Field(default_factory=list)


class MyContentListResponse(BaseModel):
    items: list[MyContentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
