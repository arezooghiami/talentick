"""
Talentick — Progress Tracking Schemas
========================================
پیشرفت کاربر در سطح آیتم (UserItemProgress) و کل محتوا (UserContentProgress).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

PROGRESS_STATUSES = ("not_started", "in_progress", "completed")


class ItemProgressUpdate(BaseModel):
    """درخواست به‌روزرسانی پیشرفت یک آیتم — از پرتال کاربر (My Contents)."""

    progress_pct: int = Field(..., ge=0, le=100, description="درصد پیشرفت این آیتم")
    position: Optional[int] = Field(None, ge=0, description="آخرین محل مشاهده (ثانیه ویدیو، شماره صفحه و ...)")
    view_time_seconds: Optional[int] = Field(
        None, ge=0, description="زمان مشاهده‌شده در این تعامل (ثانیه) — به مجموع قبلی اضافه می‌شود"
    )


class ItemProgressResponse(BaseModel):
    item_id: str
    status: str
    progress_pct: int
    last_position: Optional[int] = None
    view_time_seconds: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_viewed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ContentProgressResponse(BaseModel):
    content_id: str
    status: str
    progress_pct: int
    completed_items: int
    total_items: int
    total_view_time_seconds: int
    last_item_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_viewed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
