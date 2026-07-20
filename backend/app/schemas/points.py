"""
Talentick — Points (Gamification) Schemas
=============================================
PointRule (سراسری، مدیریت super_admin) + PointsLedgerEntry (دفترکل شخصی هر کاربر).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

EVENT_TYPE_LABEL_FA = {
    "content_item_completed": "تکمیل آیتم محتوا",
    "content_completed": "تکمیل کامل محتوا",
    "quiz_passed": "قبولی در آزمون",
    "onboarding_step_completed": "تکمیل مرحله‌ی آنبوردینگ",
    "onboarding_program_completed": "تکمیل کامل برنامه‌ی آنبوردینگ",
}

ROLE_LABEL_FA = {
    "super_admin": "سوپر ادمین",
    "org_admin": "ادمین سازمان",
    "manager": "منیجر",
    "employee": "کارمند",
}


class PointRuleResponse(BaseModel):
    id: str
    event_type: str
    event_label: str
    points: int
    is_active: bool

    model_config = {"from_attributes": True}


class PointRuleUpdate(BaseModel):
    points: Optional[int] = Field(None, ge=0, le=1000)
    is_active: Optional[bool] = None


class PointsLedgerEntryResponse(BaseModel):
    id: str
    event_type: str
    event_label: str
    reference_id: str
    reference_title: Optional[str] = None
    points: int
    created_at: datetime

    model_config = {"from_attributes": True}


class PointsHistoryResponse(BaseModel):
    items: list[PointsLedgerEntryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class PointsSummaryResponse(BaseModel):
    total_points: int


class PointGroupOverrideCreate(BaseModel):
    event_type: str
    target_type: str = Field(..., description="role | department")
    target_value: str = Field(..., description="نام نقش برای role — UUID واحد سازمانی برای department")
    points: int = Field(..., ge=0, le=1000)


class PointGroupOverrideResponse(BaseModel):
    id: str
    event_type: str
    event_label: str
    target_type: str
    target_value: str
    target_label: Optional[str] = None
    points: int
    is_active: bool

    model_config = {"from_attributes": True}
