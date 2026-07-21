"""
Talentick — Reward Marketplace Schemas
===========================================
بخش پنجم/ششم اسپک — فروشگاه جایزه + گردش درخواست تبدیل امتیاز.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

REWARD_CATEGORY_LABEL_FA = {
    "goods": "کالا",
    "gift_card": "کارت هدیه",
    "cash": "جایزه نقدی",
    "course": "دوره آموزشی",
    "benefit": "مزایا و خدمات",
    "special_access": "دسترسی ویژه",
    "leave": "مرخصی تشویقی",
    "custom": "سایر",
}

REDEMPTION_STATUS_LABEL_FA = {
    "draft": "پیش‌نویس",
    "submitted": "ثبت‌شده",
    "under_review": "در حال بررسی",
    "approved": "تایید شده",
    "rejected": "رد شده",
    "delivered": "تحویل داده شده",
    "cancelled": "لغو شده",
}


class RewardCreate(BaseModel):
    org_id: Optional[str] = Field(None, description="خالی = سراسری (فقط super_admin مجاز است) — org_admin همیشه سازمان خودش")
    title: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    category: str = Field("custom")
    image_url: Optional[str] = Field(None, max_length=500)
    cost_points: int = Field(..., gt=0, le=1000000)
    inventory_total: Optional[int] = Field(None, ge=0, description="خالی = نامحدود")
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: str = Field("active")


class RewardUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    category: Optional[str] = None
    image_url: Optional[str] = Field(None, max_length=500)
    cost_points: Optional[int] = Field(None, gt=0, le=1000000)
    inventory_total: Optional[int] = Field(None, ge=0)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Optional[str] = None


class RewardResponse(BaseModel):
    id: str
    org_id: Optional[str] = None
    org_name: Optional[str] = None
    title: str
    description: Optional[str] = None
    category: str
    category_label: str
    image_url: Optional[str] = None
    cost_points: int
    inventory_total: Optional[int] = None
    inventory_remaining: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: str
    is_available: bool = Field(..., description="فعال، در بازه‌ی زمانی، و موجودی>۰ (یا نامحدود)")
    created_at: datetime

    model_config = {"from_attributes": True}


class RewardListResponse(BaseModel):
    items: list[RewardResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class RedemptionCreate(BaseModel):
    reward_id: str
    quantity: int = Field(1, ge=1, le=100)
    user_note: Optional[str] = Field(None, max_length=1000)
    submit: bool = Field(True, description="False = ذخیره به‌عنوان Draft بدون ارسال")


class RedemptionDecision(BaseModel):
    admin_note: Optional[str] = Field(None, max_length=1000)


class RedemptionResponse(BaseModel):
    id: str
    org_id: str
    user_id: str
    user_name: Optional[str] = None
    reward_id: str
    reward_title: Optional[str] = None
    reward_image_url: Optional[str] = None
    status: str
    status_label: str
    quantity: int
    cost_points_snapshot: int
    user_note: Optional[str] = None
    admin_note: Optional[str] = None
    submitted_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    decided_by_name: Optional[str] = None
    delivered_by_name: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RedemptionListResponse(BaseModel):
    items: list[RedemptionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
